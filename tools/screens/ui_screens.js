// Screenshots of every state of the Blaze page, plus a manifest saying what to look at in each.
//
//   BASE_URL=http://127.0.0.1:8765 OUT=screens/page node tools/screens/ui_screens.js
//
// Env: BASE_URL (default http://127.0.0.1:8765), OUT (default screens/page), CHANNEL (e.g. "chrome": a real Chrome plays
// the mp4 in the finished-video screen; the bundled headless Chromium cannot decode H.264), MAKE=0 to skip making a video.
// `playwright` is found through NODE_PATH or a node_modules above this file.
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const BASE = process.env.BASE_URL || "http://127.0.0.1:8765";
const OUT = path.resolve(process.env.OUT || "screens/page");
const CHANNEL = process.env.CHANNEL || undefined;
const MAKE = process.env.MAKE !== "0";
fs.mkdirSync(OUT, { recursive: true });

const manifest = [];
let failed = 0;

async function shot(page, file, title, check) {
  await page.screenshot({ path: path.join(OUT, file + ".png") });
  manifest.push({ file: file + ".png", title, check });
  console.log("  ok  " + file);
}
const expect = (cond, msg) => { if (!cond) throw new Error("expected: " + msg); };
const textOf = (p, sel) => p.evaluate((s) => (document.querySelector(s) || {}).innerText || "", sel);
async function step(name, title, check, fn) {
  if (process.env.ONLY && !process.env.ONLY.split(",").includes(name)) return;   // ONLY=10,11 to redo some screens
  try { await fn(); } catch (e) {
    failed++; manifest.push({ file: "", title, check, error: String(e.message || e).split("\n")[0] });
    console.log("  FAIL " + name + ": " + String(e.message || e).split("\n")[0]);
  }
}

(async () => {
  const browser = await chromium.launch({ channel: CHANNEL });
  const ctx = async (scheme = "light", w = 1280, h = 800) => (await browser.newContext({ viewport: { width: w, height: h }, colorScheme: scheme })).newPage();
  const load = async (p) => { await p.goto(BASE); await p.waitForSelector("#text"); await p.waitForTimeout(500); };
  const SAMPLE = (await (await fetch(BASE + "/api/status")).json()).sample;
  const useExample = async (p) => { await p.fill("#text", SAMPLE); await p.waitForTimeout(700); await p.evaluate(() => { const t = document.getElementById("text"); t.scrollTop = 0; t.setSelectionRange(0, 0); }); };

  let p = await ctx();
  await step("01", "Fresh page", "Quiet and uncluttered. A message at the bottom offers an example. Make video is greyed out. The AI row asks you to choose a provider.", async () => {
    await load(p); await shot(p, "01-empty", "Fresh page", "");
  });
  await step("02", "Example loaded", "The editor shows the screenplay in a monospace face; the right side lists the title, cast and scenes; the bottom line counts scenes and gives a time estimate.", async () => {
    await useExample(p); await shot(p, "02-example", "Example loaded", "");
  });
  await step("03", "A mistake", "The bottom line is red, names the problem, and has a Go to line button. Make video is disabled.", async () => {
    await p.fill("#text", "JOHN: Hello.\n[ENTER JOHN left]\n"); await p.waitForTimeout(700);
    expect((await textOf(p, "#status")).includes("Go to line 2"), "the status line names line 2 with a Go to line button");
    expect(await p.isDisabled("#make"), "Make video is disabled while there is a mistake");
    await shot(p, "03-error", "A mistake", "");
  });
  await step("04", "A warning", "Heads up appears on the right for a line that is skipped; Make video stays enabled.", async () => {
    await p.fill("#text", "STYLE: dramatic\nJOHN: Hello.\nMARY: Hi.\n"); await p.waitForTimeout(700);
    expect((await textOf(p, "#outline")).includes("Heads up"), "a Heads up list for the unsupported STYLE line");
    expect(!(await p.isDisabled("#make")), "Make video stays enabled for a warning");
    await shot(p, "04-warning", "A warning", "");
  });
  await step("05", "Format help", "The Screenplay format list opens on the right and reads clearly.", async () => {
    await useExample(p); await p.click("summary"); await p.waitForTimeout(300); await shot(p, "05-format-help", "Format help open", "");
  });
  await step("06", "Choosing an AI provider", "The provider menu and a key field (shown as dots) sit above the editor; nothing is preselected before you choose.", async () => {
    await p.selectOption("#prov", "anthropic"); await p.fill("#provKey", "sk-ant-demo-key-not-real"); await p.waitForTimeout(300); await shot(p, "06-ai-choose", "Choosing an AI provider", "");
  });
  await step("07", "AI ready", "After Save the row becomes a box to describe a story, with Short scene / Whole story and Change provider.", async () => {
    await p.click("#provSave"); await p.waitForSelector("#idea:not([hidden])", { timeout: 8000 });
    await p.selectOption("#ideaMode", "whole"); await p.fill("#ideaText", "two friends find a message in a bottle"); await p.waitForTimeout(300);
    await shot(p, "07-ai-ready", "AI ready", "");
  });

  if (MAKE) {
    await step("08", "Making a video", "A thin blue progress line grows under the top bar; the right side says what is happening; the button says Making.", async () => {
      await p.fill("#text", fs.readFileSync(path.join(__dirname, "..", "..", "tests", "fixtures", "sample_story.txt"), "utf8"));
      await p.waitForTimeout(500); await p.selectOption("#quality", "fast"); await p.uncheck("#voice");
      await p.click("#make"); await p.waitForTimeout(5000); await shot(p, "08-making", "Making a video", "");
    });
    await step("09", "Finished video", "The video appears in a player with Download video, Subtitles and its length. (With a real Chrome the player shows a frame; the bundled headless Chromium cannot play H.264 and shows black.)", async () => {
      await p.waitForSelector("video", { timeout: 600000 });
      await p.evaluate(() => { const v = document.querySelector("video"); v.muted = true; v.currentTime = 12; });
      await p.waitForTimeout(1500); await shot(p, "09-done", "Finished video", "");
      const playable = await p.evaluate(() => document.querySelector("video").readyState >= 2);
      manifest[manifest.length - 1].playable = playable;
      console.log("  video playable in this browser:", playable);
    });
  }

  await step("10", "Dark theme", "Same page in dark: text and the editor stay readable, the button inverts.", async () => {
    const d = await ctx("dark"); await load(d); await useExample(d); await shot(d, "10-dark", "Dark theme", ""); await d.context().close();
  });
  await step("11", "Phone width", "One column: the editor first, the outline below; nothing is cut off.", async () => {
    const m = await ctx("light", 390, 844); await load(m); await useExample(m); await shot(m, "11-phone", "Phone width", ""); await m.context().close();
  });
  await step("12", "Tablet width", "A comfortable single column or two columns, no horizontal scrolling.", async () => {
    const t = await ctx("light", 820, 1180); await load(t); await useExample(t); await shot(t, "12-tablet", "Tablet width", ""); await t.context().close();
  });

  await step("13", "A misspelt name or command", "The status line is red and names the line: an undeclared speaker, a command that names nobody, and an unknown command each get their own message and, where there is one, a suggestion. Nothing is silently turned into a new character.", async () => {
    const cases = [
      ["JOHN: Hello.\nLater that day: Mary went home\n", "is not a declared character", 2],
      ["JOHN: Hello.\n[MOVE JOHM 3]\n", "did you mean John", 2],
      ["JOHN: Hello.\n[MOV JOHN 3]\n", "did you mean MOVE", 2],
    ];
    for (const [text, says, line] of cases) {
      await p.fill("#text", text); await p.waitForTimeout(700);
      const st = await textOf(p, "#status");
      expect(st.includes(says) && st.includes("Go to line " + line), `"${says}" on line ${line}, got: ${st.slice(0, 120)}`);
      expect(await p.isDisabled("#make"), "Make video is disabled");
    }
    await shot(p, "13-names", "A misspelt name or command", "");
  });
  await step("14", "A voice for each character", "Under the outline a Voices list has one row per character: a drop-down (Automatic, Silent, then every installed voice), a Play button and a speed box. Choosing a voice writes it into that character's CAST line in the editor.", async () => {
    await load(p); await useExample(p);
    // The page asks the server to check the screenplay and then draws the rows. A fixed pause is enough on a quick machine
    // and not on a slow one (the installed app on Windows lists the system voices first), so wait for the rows instead.
    await p.waitForSelector("#voicebox li", { timeout: 30000 }).catch(() => {});
    const rows = await p.$$("#voicebox li");
    expect(rows.length >= 2, "a row for each character in the example, got " + rows.length + " after waiting 30 s; status: " + (await textOf(p, "#status")).slice(0, 100));
    const select = await rows[0].$("select");
    const options = await select.$$eval("option", (o) => o.map((x) => x.value));
    expect(options[0] === "auto" && options[1] === "off", "Automatic and Silent come first");
    const real = options.find((v) => v.includes(":") && !v.includes("not installed"));
    if (real) {
      await select.selectOption(real); await p.waitForTimeout(800);
      const text = await p.inputValue("#text");
      expect(text.includes("voice=" + real), "the CAST line now says voice=" + real);
      expect(!(await p.isDisabled("#make")), "the screenplay is still valid");
      const play = await p.$("#voicebox li .play");
      await play.click();
      await p.waitForFunction(() => !document.querySelector("#voicebox .play").disabled, null, { timeout: 30000 });
      const err = await textOf(p, "#status");
      expect(!/could not|not installed|no audio/i.test(err), "Play worked, status says: " + err.slice(0, 100));
      console.log("  voice chosen and played:", real);
    } else {
      expect((await textOf(p, "#voicebox")).includes("No voice engine"), "with no engine installed the list says so");
      console.log("  no voice engine on this machine: checked the empty state instead");
    }
    await shot(p, "14-voices", "A voice for each character", "");
  });
  await step("15", "Text looks and per-character speed", "A screenplay with DEFINE LOOK lines and look= on lines checks out: the outline lists the characters with a voice row each, and nothing is flagged.", async () => {
    const demo = fs.readFileSync(path.join(__dirname, "..", "..", "examples", "looks-and-voices.txt"), "utf8");
    await p.fill("#text", demo); await p.waitForTimeout(900);
    await p.waitForFunction(() => document.querySelectorAll("#voicebox li").length === 3, null, { timeout: 30000 }).catch(() => {});
    const st = await textOf(p, "#status");
    expect(!/not a declared|unknown|is not defined/i.test(st) && !(await p.isDisabled("#make")), "the looks demo is accepted, status: " + st.slice(0, 100));
    expect((await p.$$("#voicebox li")).length === 3, "John, Mary and the Narrator each get a voice row");
    await p.evaluate(() => { const t = document.getElementById("text"); t.scrollTop = 0; t.setSelectionRange(0, 0); });
    await shot(p, "15-looks", "Text looks and per-character speed", "");
  });

  // The three modes, and your own characters
  const ROBO_PNG = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAFAAAACQCAYAAACf+ewZAAABfklEQVR42u3cvU0DQRCA0bsRdRARUAQxMUVQAgElOKAEF0FMTBEERDQCJSCQZ2c8fl9seXef936ss7xtkiRJusT2bhO6f/n8/u01b083O8A/onXF3M8VrgtkTMDLeL/WgFmLrUCMKXhViDEJrwIxpuGtHi8m4q0cN6birRo/NvUFrN59K+ZhBwIcCtjl8M2ejx0IECBAgAIIECDAk9bp0WPmfOxAgIMBuxzGmfOwA7sDVu/C7PFjwiIqx41Ji6kYLyYuauWHFdMOq9U7veQqnLXIinNt2W3MqRdbdaHyC9VzAax4SjfqNsY3EQEECBCgAAIECFAAAQIEKIAAAQIEKIAAAQIUQIAAAQogQIAABRAgQIACCBAgQAEECBCgAAIECFAAAQIEKIAAAQIUQIAAAQogQIAAAQpgVVerB/x6PaSPcf3wvGw9y/9/9PbuMf2vQD/ej7tD2DkQoAACBAhQAAECBCiAAAECFECAAAEKIECAAAUQIECAABEAlKT/9gOWM2QH5jwMkwAAAABJRU5ErkJggg==", "base64");
  await step("16", "Your own character", "The Characters panel lists a character you added (a small picture on a checkerboard so you can see it is transparent), with Use, + mouth and Remove. Before it was added, the status line said there was no such character in the library; afterwards that message is gone.", async () => {
    await p.selectOption("#quality", "fast");
    await p.fill("#text", "TITLE: Robo\nCAST: ROBO asset=robo\nCAST: MARY gender=f dress=1\nSCENE: lab\nROBO: Good morning.\nMARY: You are late, Robo.\n"); await p.waitForTimeout(800);
    expect(/no character 'robo'/.test(await textOf(p, "#status")), "a missing library character is reported while typing: " + (await textOf(p, "#status")).slice(0, 100));
    const [fc] = await Promise.all([p.waitForEvent("filechooser"), p.click("#addChar")]);
    await fc.setFiles({ name: "robo.png", mimeType: "image/png", buffer: ROBO_PNG });
    await p.waitForSelector("#library li[data-name=robo]"); await p.waitForTimeout(900);
    expect(!/no character/.test(await textOf(p, "#status")), "after adding it the message goes away: " + (await textOf(p, "#status")).slice(0, 100));
    expect(!(await p.isDisabled("#make")), "Make video is available");
    await p.evaluate(() => document.getElementById("library").scrollIntoView());
    await shot(p, "16-library", "Your own character", "");
  });
  await step("17", "Editor mode", "Just the code: line numbers on the left, no side panel, the line with the mistake numbered in red and named in the status line.", async () => {
    await p.click("#tab-editor"); await p.fill("#text", "ROBO: hi\n[MOV ROBO 3]\n"); await p.waitForTimeout(800);
    expect(!(await p.isVisible("aside")), "the side panel is hidden");
    expect((await textOf(p, "#gutter .bad")) === "2", "line 2 is marked in the gutter");
    expect(/unknown command/.test(await textOf(p, "#status")), "the status line names the mistake");
    await shot(p, "17-editor", "Editor mode", "");
  });
  if (MAKE) {
    await step("18", "Running mode", "The finished video with a timeline under it: a Scenes row (the title card, then each scene), and one row per speaker with a block for every line, a red playhead, a list of lines on the right, and Play, speed, zoom, Download. (The bundled headless Chromium cannot play H.264, so the picture is black here; the timeline does not depend on it.)", async () => {
      await p.click("#tab-running"); await p.waitForSelector("#tlInner .blk", { timeout: 20000 });
      expect((await p.$$(".blk.scene")).length === 4, "title card and three scenes on the Scenes row, got " + (await p.$$(".blk.scene")).length);
      expect((await p.$$("#lineList li[data-i]")).length > 5, "the sample story's lines are listed");
      expect((await p.$$(".tlrow")).length >= 4, "a row per speaker under Scenes");
      await p.click(".blk:not(.scene)"); await p.waitForTimeout(300);
      await shot(p, "18-running", "Running mode", "");
    });
  }
  await p.click("#tab-smart"); await p.evaluate(async () => { await fetch("/api/library/remove", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ kind: "character", name: "robo" }) }); });

  fs.writeFileSync(path.join(OUT, "manifest.json"), JSON.stringify(manifest, null, 2));
  await browser.close();
  console.log(failed ? `${failed} screen(s) failed` : "all screens captured");
  process.exit(failed ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
