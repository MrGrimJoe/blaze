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

console.log("\n" + n + " tests passed");
