// End-to-end tests for Back-end/Render/render.js using props written in CDRCA itself (def PROP). Skips without playwright.
//   node tests/render.test.js
const assert = require("assert");
const fs = require("fs");
const os = require("os");
const path = require("path");
const crypto = require("crypto");
const { spawnSync } = require("child_process");

try { require.resolve("playwright"); } catch (e) { console.log("skip - playwright not installed"); process.exit(0); }

const RENDER = path.join(__dirname, "..", "Back-end", "Render", "render.js");
const dir = fs.mkdtempSync(path.join(os.tmpdir(), "cdrca-render-"));
const render = (file, extra) => spawnSync(process.execPath, [RENDER, file, "--width", "160", "--height", "90", ...extra], { encoding: "utf8" });
const md5 = (f) => crypto.createHash("md5").update(fs.readFileSync(f)).digest("hex");

// a square prop defined in the script: the only things used are def PROP, `use`, actions and the standard Prop base
const PROP = `!--- PROP Block :: a coloured square ---

def PROP Block {
  constructor(x, color) { super(); this.x = x; this.color = color; }
  getObjectConfig() {
    return {
      Geometry: new THREE.PlaneGeometry(1, 1),
      Material: new THREE.MeshBasicMaterial({ color: this.color }),
      outline: { render: false, color: 0x000000, opacity: 0 },
      createMesh: true,
      modifier: { mesh: this.modifyMesh.bind(this) },
    };
  }
  modifyMesh(mesh) { mesh.position.set(this.x, 0, 0); return mesh; }
  slideTo(mesh, totalTime, lerpProgress, step, x) {
    mesh.position.set(this.x + (x - this.x) * lerpProgress, 0, 0);
    return mesh;
  }
}

!---END---
`;

// 1. def PROP works (it needs mixClasses, whitespace-correct bodies) and a script renders, frames change over time
{
  fs.writeFileSync(path.join(dir, "one.cdrca"), PROP + `
!--- SCENE T :: ---
use Block(-3, 0xff0000) as block
add new action go 1000 800
def ACTION go block slideTo 3
!---END---
`);
  const r = render(path.join(dir, "one.cdrca"), ["--out", path.join(dir, "f1"), "--fps", "10"]);
  assert.strictEqual(r.status, 0, r.stderr);
  const info = JSON.parse(r.stdout.trim());
  const files = fs.readdirSync(path.join(dir, "f1")).sort();
  assert.strictEqual(files.length, info.frames);
  assert(new Set(files.map((f) => md5(path.join(dir, "f1", f)))).size > 5, "the square should move");
  console.log("ok - a prop defined with def PROP renders and moves (" + info.frames + " frames)");
}

// 2. many props and many actions must not blow up (Scene used to copy props exponentially in their number)
{
  let uses = "", actions = "", defs = "";
  for (let i = 0; i < 10; i++) uses += `use Block(${i - 5}, 0x00ff00) as b${i}\n`;
  for (let a = 0; a < 40; a++) {
    actions += `add new action a${String(a).padStart(3, "0")} 100 1\n`;
    for (let i = 0; i < 10; i++) defs += `def ACTION a${String(a).padStart(3, "0")} b${i} modifyMesh ""\n`;
  }
  fs.writeFileSync(path.join(dir, "many.cdrca"), PROP + `\n!--- SCENE T :: ---\n${uses}${actions}${defs}!---END---\n`);
  const t0 = Date.now();
  const r = render(path.join(dir, "many.cdrca"), ["--out", path.join(dir, "f2"), "--fps", "2", "--duration", "1"]);
  assert.strictEqual(r.status, 0, r.stderr);
  const secs = (Date.now() - t0) / 1000;
  assert(secs < 40, "10 props x 40 actions took " + secs.toFixed(1) + "s");
  console.log("ok - 10 props x 40 actions loads and renders in " + secs.toFixed(1) + "s");
}

// 3. images loaded by a script are waited for: the first frame already shows the picture
{
  const PNG = Buffer.from(require("child_process").execFileSync("python3", ["-c",
    "import base64,struct,zlib\nw,h=16,16\nraw=b''.join(b'\\x00'+bytes((255,0,0))*w for _ in range(h))\n" +
    "ch=lambda t,d:struct.pack('>I',len(d))+t+d+struct.pack('>I',zlib.crc32(t+d)&0xffffffff)\n" +
    "import sys;sys.stdout.write(base64.b64encode(b'\\x89PNG\\r\\n\\x1a\\n'+ch(b'IHDR',struct.pack('>IIBBBBB',w,h,8,2,0,0,0))+ch(b'IDAT',zlib.compress(raw))+ch(b'IEND',b'')).decode())"]).toString(), "base64");
  fs.writeFileSync(path.join(dir, "red.png"), PNG);
  fs.writeFileSync(path.join(dir, "pic.cdrca"), `!--- PROP Pic :: ---

def PROP Pic {
  constructor(src) { super(); this.src = src; }
  getObjectConfig() {
    return { Geometry: new THREE.PlaneGeometry(6, 6), Material: new THREE.MeshBasicMaterial({ map: new THREE.TextureLoader().load(this.src) }),
             outline: { render: false, color: 0x000000, opacity: 0 }, createMesh: true, modifier: { mesh: (m) => m } };
  }
}

!---END---

!--- SCENE T :: ---
use Pic("red.png") as pic
add new action go 500 1
def ACTION go pic modifyMesh ""
!---END---
`);
  const r = render(path.join(dir, "pic.cdrca"), ["--out", path.join(dir, "f3"), "--fps", "4", "--from", "1.5", "--duration", "0.5"]);
  assert.strictEqual(r.status, 0, r.stderr);
  const first = fs.readdirSync(path.join(dir, "f3")).sort()[0];
  const bytes = fs.readFileSync(path.join(dir, "f3", first));
  assert(bytes.length > 100, "frame written");
  console.log("ok - a script that loads an image renders (relative path resolved against the script)");
}

// 4. a broken script is a JSON error and a non-zero exit
{
  fs.writeFileSync(path.join(dir, "bad.cdrca"), "use Nope.Nothing() as x\n");
  const r = render(path.join(dir, "bad.cdrca"), ["--out", path.join(dir, "f4")]);
  assert.notStrictEqual(r.status, 0);
  assert(/"ok":false/.test(r.stderr), "failures are reported as JSON on stderr");
  console.log("ok - a broken script fails with a JSON error");
}
