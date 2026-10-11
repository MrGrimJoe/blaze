// Plain-node regression tests for the transpiler (no dependencies):  node tests/transpiler.test.js
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const { transpile } = require("../Back-end/Transpiler/index.js");

const demo = fs.readFileSync(path.join(__dirname, "..", "examples", "demo_animation.cdrca"), "utf8");
const run = (src) => transpile({ "index.cdrca": src });
// the body of the LAST `function <name>` (the one that wins in JS)
const lastFn = (js, name) => {
  const parts = js.split("function " + name + "(").slice(1);
  assert(parts.length > 0, "no function " + name);
  return parts[parts.length - 1].split("\nfunction ")[0].split("var ")[0];
};
const guards = (body) => (body.match(/if \(index === (\d+)\)/g) || []).map((m) => m.match(/\d+/)[0]);

let n = 0;
const test = (name, fn) => { fn(); n++; console.log("ok -", name); };

test("def ACTION: each part only drives the prop it names", () => {
  const js = run(demo);
  assert.deepStrictEqual(guards(lastFn(js, "bounce1")), ["0"]);   // ball only
  assert.deepStrictEqual(guards(lastFn(js, "spin")), ["1"]);      // cube only
});

test("def ACTION: lines sharing a name combine (demo 'combo' = both props)", () => {
  assert.deepStrictEqual(guards(lastFn(run(demo), "combo")).sort(), ["0", "1"]);
});

test("def ACTION: parts do not leak between transpile() calls", () => {
  run(demo);
  assert.deepStrictEqual(guards(lastFn(run(demo), "combo")).sort(), ["0", "1"]);
  const other = run("!--- SCENE a :: x ---\nuse ObjectAnimationSystem_INS.CORE_3d_PROPSsceneSYS.exampleProps.BouncingSphereProp() as ball\nadd new action combo 1000 100\ndef ACTION combo ball modifyMesh \"\"\n!---END---\n");
  assert.deepStrictEqual(guards(lastFn(other, "combo")), ["0"]);
});

test("scene options: documented defaults are emitted when a scene sets none", () => {
  const js = run(demo);
  for (const [k, v] of [["stayTimeInit", 1000], ["stayTimeEnd", 1000], ["lerpTime", 500], ["backgroundColor", 0]]) {
    assert(new RegExp(k + ":\\s*" + v + "\\b").test(js), "missing default " + k);
  }
});

test("def ACTION: negative numbers are one parameter (and several parts per line still work)", () => {
  const P = "ObjectAnimationSystem_INS.CORE_3d_PROPSsceneSYS.exampleProps.";
  const js = run("!--- SCENE a :: x ---\nuse " + P + "BouncingSphereProp() as ball\nuse " + P + "RotatingCubeProp(0xff0000, 1) as cube\nadd new action go 1000 100\ndef ACTION go ball modifyMesh -1.5 cube modifyMesh 2\n!---END---\n");
  assert(/propsARR\[0\]\.modifyMesh\(mesh, totalTime, lerpProgress, step, -1\.5\)/.test(js), "ball part should get -1.5");
  assert(/propsARR\[1\]\.modifyMesh\(mesh, totalTime, lerpProgress, step, 2\)/.test(js), "cube part should get 2");
});

test("JS { } blocks are emitted (they were parsed, then dropped), before the definitions", () => {
  const P = "ObjectAnimationSystem_INS.CORE_3d_PROPSsceneSYS.exampleProps.";
  const js = run("JS { globalThis.zzMarker = 40 + 2; }\n!--- SCENE a :: x ---\nuse " + P + "BouncingSphereProp() as ball\n!---END---\n");
  assert(js.includes("globalThis.zzMarker"), "the JS block should be in the output");
  assert(js.indexOf("zzMarker") < js.indexOf("var ball"), "and run before the props are created");
  vm_run(js);
  function vm_run(code) { // the block really executes (as an IIFE: it can set globals, but its own vars stay local)
    const ctx = { globalThis: null };
    new Function("globalThis", "var ObjectAnimationSystem_INS={CORE_3d_PROPSsceneSYS:{exampleProps:{BouncingSphereProp:function(){}}}};var THREE={DataTexture:function(){},RGBFormat:0};var currentANIM;" + code.replace(/currentANIM = [^;]*;/, "") )(ctx);
    assert.strictEqual(ctx.zzMarker, 42);
  }
});

test("def PROP / JS bodies keep the spaces between words (they were glued together)", () => {
  const js = run("def PROP Tiny {\n  constructor(a) { super(); for (const word of String(a).split(\" \")) { this.last = word; } }\n  size() { let total = 0; return total + 1; }\n}\nJS { const answer = 40 + 2; globalThis.zz = answer; }\n");
  assert(/for \(const word of String/.test(js), "'const word of' must not become 'constwordof'");
  assert(/let total = 0; return total \+ 1/.test(js));
  assert(/const answer = 40 \+ 2/.test(js));
  new Function("class Prop{}; const mixClasses=(c)=>c[0];" + js.replace(/ObjectAnimationSystem_INS\.CORE_3d_PROPSsceneSYS\.Prop/g, "Prop")); // parses as JavaScript
});

test("a header block that only defines things is not a scene (no empty scene is played)", () => {
  const lib = "!--- PROP Dot :: a prop ---\ndef PROP Dot {\n  constructor() { super(); }\n}\n!---END---\n";
  const scenes = (js) => (js.match(/PropsDef:/g) || []).length;
  const withUse = "!--- SCENE s1 ---\nuse Dot() as dot1\nadd new action go 1000 100\ndef ACTION go dot1 modifyMesh \"\"\n!---END---\n";
  assert.strictEqual(scenes(run(lib)), 0, "define-only block must not become a scene");
  assert.strictEqual(scenes(run(lib + withUse)), 1, "only the block that uses a prop is a scene");
  assert.strictEqual(scenes(run(withUse)), 1, "a scene that uses a prop is still a scene");
});

console.log("\n" + n + " tests passed");
