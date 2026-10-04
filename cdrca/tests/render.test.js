// End-to-end smoke test for Back-end/Render/render.js (ImageProp, TextProp, actions). Skips if playwright is missing.
//   node tests/render.test.js
const assert = require("assert");
const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawnSync } = require("child_process");

try { require.resolve("playwright"); } catch (e) { console.log("skip - playwright not installed"); process.exit(0); }

// 8x16 solid PNG, base64 (kept tiny so the test needs no assets)
const PNG = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAgAAAAQCAIAAACk6KkqAAAAE0lEQVR4nGM4YWODFTGMSgyEBABO46ABoIbkdAAAAABJRU5ErkJggg==", "base64");
const dir = fs.mkdtempSync(path.join(os.tmpdir(), "cdrca-render-"));
fs.mkdirSync(path.join(dir, "assets"));
fs.writeFileSync(path.join(dir, "assets", "a.png"), PNG);
const P = "ObjectAnimationSystem_INS.CORE_3d_PROPSsceneSYS.exampleProps.";
fs.writeFileSync(path.join(dir, "main.cdrca"), `!--- SCENE T :: test ---
use ${P}ImageProp("assets/a.png", -3, 0, 2, 0, "assets/a.png") as hero
use ${P}TextProp(0, 1, 0.4, "bubble") as label
add new action one 800 1
add new action two 800 1
def ACTION one hero modifyMesh ""
def ACTION one label say "hello there"
def ACTION two hero moveTo 3
def ACTION two label modifyMesh ""
!---END---
`);
const out = path.join(dir, "frames");
const r = spawnSync(process.execPath, [path.join(__dirname, "..", "Back-end", "Render", "render.js"), path.join(dir, "main.cdrca"),
  "--out", out, "--fps", "10", "--width", "160", "--height", "90", "--format", "png"], { encoding: "utf8" });
assert.strictEqual(r.status, 0, r.stderr);
const info = JSON.parse(r.stdout.trim());
const files = fs.readdirSync(out).sort();
assert.strictEqual(files.length, info.frames);
assert(info.frames >= 20, "expected the whole animation (intro + 2 actions + end), got " + info.frames + " frames");
const md5 = (f) => require("crypto").createHash("md5").update(fs.readFileSync(path.join(out, f))).digest("hex");
assert(new Set(files.map(md5)).size > 5, "frames should change over time (walk + text)");
console.log("ok - renders ImageProp/TextProp/actions to " + info.frames + " distinct frames");

const bad = path.join(dir, "bad.cdrca");
fs.writeFileSync(bad, "use Nope.Nothing() as x\n");
const rb = spawnSync(process.execPath, [path.join(__dirname, "..", "Back-end", "Render", "render.js"), bad, "--out", path.join(dir, "f2")], { encoding: "utf8" });
assert.notStrictEqual(rb.status, 0);
assert(/"ok":false/.test(rb.stderr), "failures are reported as JSON on stderr");
console.log("ok - a broken script fails with a JSON error");
