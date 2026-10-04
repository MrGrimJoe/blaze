#!/usr/bin/env node
/**
 * Headless, frame-exact renderer: turns a .cdrca file into image frames (and optionally an mp4).
 *
 *   node Back-end/Render/render.js <file.cdrca> --out frames/ [--fps 24] [--width 1280] [--height 720]
 *                                  [--duration <sec>] [--from <sec>] [--format png|jpeg] [--video out.mp4]
 *
 * Needs `npm i playwright` (+ `npx playwright install chromium`) and, for --video, ffmpeg on PATH.
 *
 * It runs the unmodified Front-end/three.js and Front-end/Renderer.js in headless Chromium, replacing
 * requestAnimationFrame with a manual clock so every frame is rendered at an exact timestamp
 * (deterministic, not real time). Files a script refers to (e.g. ImageProp paths) are resolved
 * relative to the .cdrca file, exactly as they would be relative to a web page.
 *
 * On success prints one JSON line to stdout. On failure prints {"ok":false,"stage":...,"message":...}
 * to stderr and exits non-zero.
 */
const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");

const FRONT = path.join(__dirname, "..", "..", "Front-end");
const ORIGIN = "http://cdrca.local";
const PAGE = '<!DOCTYPE html><body style="margin:0;background:#000"><canvas id="THRREjsRender"></canvas></body>';
const MANUAL_CLOCK = `
  window.__q = [];
  window.requestAnimationFrame = (cb) => { window.__q.push(cb); return window.__q.length; };
  window.cancelAnimationFrame = () => {};
  window.__step = (t) => { const q = window.__q; window.__q = []; q.forEach((cb) => cb(t)); };
`;
// total length of the animation as the renderer will play it (intro + actions + end, per scene)
const LENGTH_SECONDS = `(() => {
  if (typeof OAS_OBJ === "undefined") return null;
  let ms = 0;
  for (const s of OAS_OBJ.scenes) {
    ms += (s.lerpTime || 0) + (s.stayTimeInit || 0) + (s.stayTimeEnd || 0);
    for (const a of s.actions || []) ms += (a.lerpTime || 0) + (a.stayTime || 0);
  }
  return ms / 1000;
})()`;

function fail(stage, message, extra) {
  process.stderr.write(JSON.stringify({ ok: false, stage, message: String(message), ...extra }) + "\n");
  process.exit(1);
}

function parseArgs(argv) {
  const a = { fps: 24, width: 1280, height: 720, out: "frames", format: "png" };
  const rest = [];
  for (let i = 0; i < argv.length; i++) {
    const k = argv[i];
    if (k === "--out") a.out = argv[++i];
    else if (k === "--fps") a.fps = Number(argv[++i]);
    else if (k === "--width") a.width = Number(argv[++i]);
    else if (k === "--height") a.height = Number(argv[++i]);
    else if (k === "--duration") a.duration = Number(argv[++i]);
    else if (k === "--from") a.from = Number(argv[++i]);
    else if (k === "--format") a.format = argv[++i];
    else if (k === "--video") a.video = argv[++i];
    else rest.push(k);
  }
  a.file = rest[0];
  return a;
}

// read the .cdrca file plus every .cdrca beside/below it, so @import / @addImport resolve
function readProject(file) {
  const dir = path.dirname(file);
  const vfs = {};
  (function walk(d, node) {
    for (const e of fs.readdirSync(d, { withFileTypes: true })) {
      if (e.name === "node_modules" || e.name.startsWith(".")) continue;
      if (e.isDirectory()) { node[e.name] = {}; walk(path.join(d, e.name), node[e.name]); }
      else if (e.name.endsWith(".cdrca")) node[e.name] = fs.readFileSync(path.join(d, e.name), "utf8");
    }
  })(dir, vfs);
  return vfs;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.file) fail("args", "usage: render.js <file.cdrca> --out frames/");
  const file = path.resolve(args.file);
  if (!fs.existsSync(file)) fail("args", "file not found: " + file);

  let js;
  try {
    const { transpile } = require("../Transpiler/index.js");
    js = transpile(readProject(file), {}, [path.basename(file)]);
    if (typeof js !== "string" || !js.trim()) throw new Error("transpiler returned no code");
  } catch (e) { fail("transpile", e.message); }

  let chromium;
  try { ({ chromium } = require("playwright")); }
  catch (e) { fail("setup", "playwright is not installed: npm i playwright && npx playwright install chromium"); }

  const outDir = path.resolve(args.out);
  fs.mkdirSync(outDir, { recursive: true });
  const ext = /^jpe?g$/.test(args.format) ? "jpg" : "png";

  // the page's URL mirrors the script's folder, so "../assets/x.png" means what it would on disk
  const dirUrl = ORIGIN + "/fs/" + path.dirname(file).replace(/\\/g, "/").replace(/^\//, "");
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  try {
    // the renderer sizes its canvas to innerWidth/2 x innerHeight/2
    const page = await browser.newPage({ viewport: { width: args.width * 2, height: args.height * 2 } });
    const errors = [];
    page.on("pageerror", (e) => errors.push(String(e)));
    page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
    await page.route(ORIGIN + "/**", (route) => {
      const u = new URL(route.request().url());
      if (u.pathname.endsWith("/index.html")) return route.fulfill({ contentType: "text/html", body: PAGE });
      const p = decodeURIComponent(u.pathname).replace(/^\/fs\//, "");
      const abs = path.resolve(process.platform === "win32" ? p : "/" + p);
      if (fs.existsSync(abs) && fs.statSync(abs).isFile()) return route.fulfill({ path: abs });
      return route.fulfill({ status: 404, body: "not found" });
    });
    await page.addInitScript(MANUAL_CLOCK);
    await page.goto(dirUrl + "/index.html");
    await page.addScriptTag({ path: path.join(FRONT, "three.js") });
    await page.addScriptTag({ path: path.join(FRONT, "Renderer.js") });
    await page.addScriptTag({ content: "let currentANIM = null;" }); // the global the editor UI defines
    try { await page.addScriptTag({ content: js }); } catch (e) { fail("run", e.message, { errors }); }
    // wait for images the script uses (ImageProp) so no frame is rendered half-loaded
    await page.evaluate(async () => {
      const P = ObjectAnimationSystem_INS.CORE_3d_PROPSsceneSYS.exampleProps;
      if (P.ImageProp && P.ImageProp.ready) await P.ImageProp.ready();
    });
    if (errors.length) fail("run", errors[0], { errors });

    // --from skips the first seconds of the animation (the clock still runs through them, so state
    // such as a walk in progress is correct); only frames after it are written, numbered from 0.
    const skip = Math.round((args.from || 0) * args.fps);
    const seconds = args.duration ?? ((await page.evaluate(LENGTH_SECONDS)) ?? 5) - (args.from || 0);
    const frames = Math.max(1, Math.round(seconds * args.fps));
    for (let i = 0; i < skip + frames; i++) {
      const t = 1000 + (i * 1000) / args.fps;
      if (i < skip) {
        await page.evaluate((t) => window.__step(t), t);
        continue;
      }
      // step and read the canvas in one task, before the drawing buffer is cleared
      const url = await page.evaluate(([t, mime]) => {
        window.__step(t);
        return document.getElementById("THRREjsRender").toDataURL(mime, 0.92);
      }, [t, ext === "jpg" ? "image/jpeg" : "image/png"]);
      fs.writeFileSync(path.join(outDir, String(i - skip).padStart(6, "0") + "." + ext), Buffer.from(url.split(",")[1], "base64"));
      if (errors.length) fail("render", errors[0], { errors, frame: i });
    }

    let video = null;
    if (args.video) {
      const r = spawnSync("ffmpeg", ["-y", "-framerate", String(args.fps), "-i", path.join(outDir, "%06d." + ext),
        "-pix_fmt", "yuv420p", path.resolve(args.video)], { encoding: "utf8" });
      if (r.status !== 0) fail("encode", (r.stderr || "ffmpeg failed").slice(-400));
      video = path.resolve(args.video);
    }
    process.stdout.write(JSON.stringify({ ok: true, frames, fps: args.fps, seconds, dir: outDir, video }) + "\n");
  } finally {
    await browser.close();
  }
}

main().catch((e) => fail("crash", e.stack || e.message));
