let ObjectAnimationSystem = function () {
  // Core renderer dont edit
  function CORE_3dFramesRenderer(FPS, loopAtEnd, ObjectsOverTime, gradientMap) {
    const DeltaFrame = 1 / FPS;
    let totalFrames = 0;
    let currentOOT = 0;
    let currentStartTime = 0;

    gradientMap.minFilter = THREE.NearestFilter;
    gradientMap.magFilter = THREE.NearestFilter;
    gradientMap.needsUpdate = true;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(
      75,
      window.innerWidth / window.innerHeight,
      0.1,
      1000
    );

    const canvas = document.getElementById("THRREjsRender");
    const renderer = new THREE.WebGLRenderer({ canvas: canvas });
    renderer.setSize(window.innerWidth / 2, window.innerHeight / 2);

    const light = new THREE.DirectionalLight(0xffffff, 1);
    light.position.set(5, 10, 7.5);
    scene.add(light);
    scene.add(light.target);
    const ambientLight = new THREE.AmbientLight(0x404040);
    scene.add(ambientLight);

    camera.position.z = 5;

    function runmodifier(modifier, params, defaultReturn) {
      return new Function(
        `return function main(${params.join(
          ","
        )}) { ${modifier}; return ${defaultReturn} }`
      )();
    }

    function addOutlineToMesh(mesh, color, opacity) {
      const outlineMaterial = new THREE.MeshBasicMaterial({
        color: color,
        side: THREE.BackSide,
        transparent: opacity < 1,
        opacity: opacity,
        depthWrite: false,
      });
      const outlineMesh = new THREE.Mesh(
        mesh.geometry.clone(),
        outlineMaterial
      );
      outlineMesh.scale.multiplyScalar(1.05);
      mesh.add(outlineMesh);
      return mesh;
    }

    function getOBJmesh(obj, totalTime, lerpProgress, step) {
      let mesh;
      if (obj.createMesh) {
        let geometry = obj.Geometry;
        let material = obj.Material.clone();
        if (obj.modifier.geometry && obj.modifier.geometry !== "") {
          geometry = runmodifier(
            obj.modifier.geometry,
            ["geometry", "material", "totalTime", "lerpProgress", "step"],
            "geometry"
          )(geometry, material, totalTime, lerpProgress, step);
        }
        mesh = new THREE.Mesh(geometry, material);
      } else {
        mesh = obj.Mesh;
      }
      if (obj.modifier.mesh) {
        if (typeof obj.modifier.mesh === "function") {
          mesh = obj.modifier.mesh(mesh, totalTime, lerpProgress, step);
        } else if (obj.modifier.mesh !== "") {
          mesh = runmodifier(
            obj.modifier.mesh,
            ["mesh", "totalTime", "lerpProgress", "step"],
            "mesh"
          )(mesh, totalTime, lerpProgress, step);
        }
      }
      if (obj.outline && obj.outline.render) {
        mesh = addOutlineToMesh(
          mesh,
          obj.outline.color,
          obj.outline.opacity * lerpProgress
        );
      }
      if (mesh.material) {
        mesh.material.transparent = true;
        mesh.material.opacity = lerpProgress;
      }
      return mesh;
    }

    let trackedScene = [];
    let framesNum_tracker = 0;
    let isTracking = true;

    function getIsTracking() {
      return isTracking;
    }

    async function getTrackedResult(endTrackingFn = () => isTracking) {
      if (!endTrackingFn(framesNum_tracker)) {
        return trackedScene;
      }

      await new Promise((resolve) => {
        requestAnimationFrame(async function () {
          await getTrackedResult(endTrackingFn);
          resolve();
        });
      });
    }

    function trackManager(doTrackFn = () => true) {
      isTracking = doTrackFn(framesNum_tracker);
      return getTrackedResult;
    }

    function addToScene(sceneINS, item) {
      sceneINS.add(item);
      if (!isTracking) return;
      if (!trackedScene[framesNum_tracker])
        trackedScene[framesNum_tracker] = [];
      trackedScene[framesNum_tracker].push(item);
    }

    function clearScene(sceneINS) {
      sceneINS.clear();
      if (!isTracking) return;
      framesNum_tracker += 1;
    }

    function updateScene(totalTime, lerpProgress) {
      scene.clear();
      scene.add(light);
      scene.add(light.target);
      scene.add(ambientLight);
      renderer.setClearColor(ObjectsOverTime[currentOOT].backgroundColor);
      const objs = ObjectsOverTime[currentOOT].Objects;
      for (let i = 0; i < objs.length; i++) {
        scene.add(getOBJmesh(objs[i], totalTime, lerpProgress, 1));
      }
    }
    var ForcedHult = false;
    function instantHault() {
      ForcedHult = true;
    }
    function instantUnhault() {
      ForcedHult = false;
    }
    function animate(timestamp) {
      if (!ForcedHult) requestAnimationFrame(animate);
      totalFrames += 1;
      if (currentStartTime === 0) currentStartTime = timestamp;

      let elapsed = timestamp - currentStartTime;
      let currentEntry = ObjectsOverTime[currentOOT];

      while (elapsed >= currentEntry.lerpTime + currentEntry.stayTime) {
        if (loopAtEnd) {
          currentOOT = (currentOOT + 1) % ObjectsOverTime.length;
        } else if (currentOOT < ObjectsOverTime.length - 1) {
          currentOOT += 1;
        } else {
          break;
        }
        currentStartTime += currentEntry.lerpTime + currentEntry.stayTime;
        elapsed = timestamp - currentStartTime;
        currentEntry = ObjectsOverTime[currentOOT];
      }

      const totalTime = timestamp / 1000;
      let lerpProgress = 1;
      if (elapsed < currentEntry.lerpTime) {
        lerpProgress = THREE.MathUtils.lerp(
          0,
          1,
          elapsed / currentEntry.lerpTime
        );
      }
      updateScene(totalTime, lerpProgress);
      renderer.render(scene, camera);
    }

    window.addEventListener("resize", () => {
      camera.aspect = window.innerWidth / window.innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(window.innerWidth, window.innerHeight);
    });

    return {
      goToNextOOT: () => currentOOT++,
      init: () => animate(0),
      instantHault,
      instantUnhault,
      getHault: () => ForcedHult,
      getIsTracking,
      trackManager,
      getTrackedResult,
    };
  }

  const CORE_3d_PROPSsceneSYS = (function () {
    class Prop {
      constructor() {
        this.initPRE();
        // super();
        this.default = {
          namePrefix: "BASIC_PROP",
        };
        this.knownProps = {};
        this.propType = [["basicProp"]]; // its a 2d arr because you have context like  type 1 -> type 2     but also type N -> Type M     so letting having mutliple tags where each tag refers to TYPE abstraction   tells exact composition of props (maybe useful in animation tracking)
        this.initPOST();
      }
      addType(type, index) {
        this.propType[Math.min(this.propType.length, index)].push(type);
      }

      initPRE() {
        // console.warn("initPRE not defined for prop", this);
      }

      initPOST() {
        // console.warn("initPRE not defined for prop", this);
      }

      getObjectConfig() {
        throw new Error(
          "getObjectConfig must be implemented for the prop",
          this
        );
      }
      modifyMesh(mesh, totalTime, lerpProgress, step) {
        return mesh;
      }
      giveMessage(message) {
        if (!message.type || !message.value) return;
        this.onmessage(message);
      }
      onmessage(message) {
        console.warn("Message was given no, handling done", message, this);
      }
      sendMessage(message, propName) {
        if (!message.type || !message.value) {
          console.warn("message invelid, message");
          return;
        }
        try {
          this.knownProps[propName].giveMessage(message);
        } catch (error1) {
          try {
            propName.giveMessage(message);
          } catch (error2) {
            console.error(
              "tried " +
                propName +
                " as name got error, tried it as prop and also got err",
              error1,
              error2,
              this
            );
          }
        }
        return;
      }
    }

    class RotatingCubeProp extends Prop {
      initPRE() {
        this.name = "rotatingCube";
      }
      initPOST() {}
      constructor(color, rotationSpeed) {
        super();
        this.color = color;
        this.rotationSpeed = rotationSpeed;
      }

      modifyMesh(mesh, totalTime) {
        mesh.rotation.x = totalTime * this.rotationSpeed;
        mesh.rotation.y = totalTime * this.rotationSpeed;
        return mesh;
      }
      getObjectConfig() {
        return {
          Geometry: new THREE.BoxGeometry(),
          Material: (() => {
            const material = new THREE.MeshToonMaterial({ color: this.color });
            material.gradientMap = this.gradientMap;
            return material;
          })(),
          outline: { render: true, color: this.color, opacity: 0.5 },
          createMesh: true,
          modifier: { mesh: this.modifyMesh.bind(this) },
        };
      }
      sampleMovementAction(mesh, totalTime, lerpProgress, step) {
        mesh.position.x = Math.sin(totalTime);
        mesh.position.y = Math.cos(totalTime);
        return mesh;
      }
    }

    class BouncingSphereProp extends Prop {
      initPRE() {
        this.name = "BouncingSphereProp";
      }
      initPOST() {}
      modifyMesh(mesh, totalTime) {
        mesh.position.y = Math.sin(totalTime) * 1;
        mesh.rotation.z = totalTime * 1.5;
        return mesh;
      }

      getObjectConfig() {
        return {
          Geometry: new THREE.SphereGeometry(0.7, 32, 32),
          Material: (() => {
            const material = new THREE.MeshToonMaterial({ color: 0xff0000 });
            material.gradientMap = this.gradientMap;
            return material;
          })(),
          outline: { render: true, color: 0xffff00, opacity: 0.5 },
          createMesh: true,
          modifier: { mesh: this.modifyMesh.bind(this) },
        };
      }
    }
    // ImageProp(src, x, y, height, z, talkSrc)
    //   A flat image standing at (x, y), `height` units tall (the width follows the image's aspect ratio).
    //   `src` is loaded like any web page asset: a URL or path relative to the page, or a data: URI.
    //   `talkSrc` (optional) is a second picture used by the `talk` action.
    // An action only drives the props it names; a prop it does not name is hidden for that action, so list
    // every prop that should stay visible (`def ACTION beat john modifyMesh ""` keeps john standing).
    // Actions:
    //   modifyMesh ""   stand at (x, y)
    //   moveTo X        walk sideways to X (units/s: ImageProp.walkSpeed), starting from where it stands
    //   talk ""         stand and flap between the two pictures (needs talkSrc)
    //   hop 0.5         jump once, this many units high (default 0.5)
    // ImageProp.ready() resolves once every image used so far has loaded (frame-exact renderers wait on it).
    class ImageProp extends Prop {
      initPRE() {
        this.name = "ImageProp";
      }
      initPOST() {}
      constructor(src, x, y, height, z, talkSrc) {
        super();
        this.src = src;
        this.x = x || 0;
        this.y = y || 0;
        this.height = height || 2;
        this.z = z || 0;
        this.talkSrc = talkSrc;
        this.walk = null;
      }
      static load(src) {
        if (!ImageProp.cache[src]) {
          ImageProp.pending.push(
            new Promise((resolve) => {
              ImageProp.cache[src] = new THREE.TextureLoader().load(
                src,
                resolve,
                undefined,
                () => {
                  console.error("ImageProp: could not load " + src);
                  resolve();
                }
              );
            })
          );
        }
        return ImageProp.cache[src];
      }
      static ready() {
        return Promise.all(ImageProp.pending);
      }
      getObjectConfig() {
        this.frames = [ImageProp.load(this.src)];
        if (this.talkSrc) this.frames.push(ImageProp.load(this.talkSrc));
        return {
          Geometry: new THREE.PlaneGeometry(1, 1),
          Material: new THREE.MeshBasicMaterial({
            map: this.frames[0],
            transparent: true,
            depthWrite: false,
            side: THREE.DoubleSide,
            visible: false, // shown once an action places it (an action only drives the props it names)
          }),
          outline: { render: false, color: 0x000000, opacity: 0 },
          createMesh: true,
          modifier: { mesh: this.modifyMesh.bind(this) },
        };
      }
      place(mesh, x, dy, frame) {
        const texture = this.frames[frame] || this.frames[0];
        const img = texture.image;
        const aspect = img && img.height ? img.width / img.height : 1;
        mesh.material.map = texture;
        mesh.material.visible = true;
        mesh.scale.set(this.height * aspect, this.height, 1);
        mesh.position.set(x, this.y + dy, this.z);
        return mesh;
      }
      modifyMesh(mesh, totalTime) {
        this.walk = null;
        this.hopT0 = null;
        return this.place(mesh, this.x, 0, 0);
      }
      talk(mesh, totalTime) {
        this.walk = null;
        this.hopT0 = null;
        const flap = Math.floor(totalTime * 8) % 2;
        return this.place(mesh, this.x, Math.abs(Math.sin(totalTime * 9)) * 0.05, flap);
      }
      hop(mesh, totalTime, lerpProgress, step, height) {
        // one jump, starting the first frame this action is seen
        if (!this.hopT0 && this.hopT0 !== 0) this.hopT0 = totalTime;
        const u = Math.min(1, (totalTime - this.hopT0) / 0.4);
        return this.place(mesh, this.x, Math.sin(Math.PI * u) * (height || 0.5), 0);
      }
      moveTo(mesh, totalTime, lerpProgress, step, x) {
        // the walk starts the first frame this action is seen; time comes from totalTime, so a
        // frame looks the same however it is reached
        if (!this.walk || this.walk.to !== x) {
          this.walk = { to: x, from: this.x, t0: totalTime };
        }
        const w = this.walk;
        const dist = Math.abs(w.to - w.from);
        const p = dist === 0 ? 1 : Math.min(1, ((totalTime - w.t0) * ImageProp.walkSpeed) / dist);
        const eased = p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2;
        const px = w.from + (w.to - w.from) * eased;
        if (p >= 1) this.x = w.to;
        this.place(mesh, px, p < 1 ? Math.abs(Math.sin(totalTime * 8)) * 0.14 : 0, 0);
        if (p < 1) mesh.rotation.z = -Math.sign(w.to - w.from) * 0.05;
        return mesh;
      }
    }
    ImageProp.cache = {};
    ImageProp.pending = [];
    ImageProp.walkSpeed = 2.4;

    // TextProp(x, y, size, style)
    //   Text shown on a flat label whose bottom-centre sits at (x, y). `size` is the height in scene
    //   units of one line of text. `style` is "bubble" (white speech bubble, the default),
    //   "caption" (dark bar) or "plain" (bare text with an outline). Hidden until it is told what to say.
    // Actions:
    //   say "text"      show the text
    //   modifyMesh ""   hide it
    class TextProp extends Prop {
      initPRE() {
        this.name = "TextProp";
      }
      initPOST() {}
      constructor(x, y, size, style) {
        super();
        this.x = x || 0;
        this.y = y || 0;
        this.size = size || 0.4;
        this.style = style || "bubble";
        this.shown = null;
      }
      getObjectConfig() {
        return {
          Geometry: new THREE.PlaneGeometry(1, 1),
          Material: new THREE.MeshBasicMaterial({
            transparent: true,
            depthWrite: false,
            depthTest: false,
            side: THREE.DoubleSide,
            visible: false,
          }),
          outline: { render: false, color: 0x000000, opacity: 0 },
          createMesh: true,
          modifier: { mesh: this.modifyMesh.bind(this) },
        };
      }
      modifyMesh(mesh) {
        mesh.material.visible = false;
        return mesh;
      }
      draw(text) {
        const FONT = 64;
        const family = '"Segoe UI","Helvetica Neue",Arial,"DejaVu Sans",sans-serif';
        const weight = this.style === "caption" ? "600 " : "700 ";
        const probe = document.createElement("canvas").getContext("2d");
        probe.font = weight + FONT + "px " + family;
        const maxW = FONT * 16;
        const lines = [];
        let line = "";
        for (const word of String(text).split(/\s+/).filter(Boolean)) {
          const trial = line ? line + " " + word : word;
          if (line && probe.measureText(trial).width > maxW) {
            lines.push(line);
            line = word;
          } else line = trial;
        }
        if (line) lines.push(line);
        const pad = FONT * 0.6;
        const tail = this.style === "bubble" ? FONT * 0.7 : 0;
        const textW = Math.max(...lines.map((l) => probe.measureText(l).width), 1);
        const w = Math.ceil(textW + pad * 2);
        const h = Math.ceil(lines.length * FONT * 1.25 + pad * 1.2 + tail);
        const canvas = document.createElement("canvas");
        canvas.width = w + 8;
        canvas.height = h + 8;
        const ctx = canvas.getContext("2d");
        ctx.font = weight + FONT + "px " + family;
        ctx.textBaseline = "middle";
        ctx.textAlign = "center";
        const boxH = h - tail;
        const round = (x, y, bw, bh, r) => {
          ctx.beginPath();
          ctx.moveTo(x + r, y);
          ctx.arcTo(x + bw, y, x + bw, y + bh, r);
          ctx.arcTo(x + bw, y + bh, x, y + bh, r);
          ctx.arcTo(x, y + bh, x, y, r);
          ctx.arcTo(x, y, x + bw, y, r);
          ctx.closePath();
        };
        if (this.style === "bubble") {
          ctx.fillStyle = "#ffffff";
          ctx.strokeStyle = "#1b1f2a";
          ctx.lineWidth = 6;
          round(4, 4, w, boxH, FONT * 0.6);
          ctx.fill();
          ctx.stroke();
          ctx.beginPath();
          ctx.moveTo(w / 2 - FONT * 0.35, boxH + 2);
          ctx.lineTo(w / 2 + 4, h + 2);
          ctx.lineTo(w / 2 + FONT * 0.35, boxH + 2);
          ctx.fillStyle = "#ffffff";
          ctx.fill();
          ctx.stroke();
          ctx.fillRect(w / 2 - FONT * 0.35 + 4, boxH, FONT * 0.7 - 4, 7);
          ctx.fillStyle = "#1b1f2a";
        } else if (this.style === "caption") {
          ctx.fillStyle = "rgba(10,12,18,0.8)";
          round(4, 4, w, boxH, FONT * 0.5);
          ctx.fill();
          ctx.fillStyle = "#ffffff";
        } else {
          ctx.fillStyle = "#ffffff";
          ctx.strokeStyle = "rgba(0,0,0,0.85)";
          ctx.lineWidth = 8;
        }
        lines.forEach((l, i) => {
          const ly = 4 + pad * 0.6 + FONT * 0.625 + i * FONT * 1.25;
          if (this.style === "plain") ctx.strokeText(l, 4 + w / 2, ly);
          ctx.fillText(l, 4 + w / 2, ly);
        });
        const texture = new THREE.CanvasTexture(canvas);
        return { texture, aspect: canvas.width / canvas.height, lines: lines.length, pxHeight: canvas.height };
      }
      say(mesh, totalTime, lerpProgress, step, text) {
        if (!this.shown || this.shown.text !== text) {
          this.shown = { text: text, ...this.draw(text) };
        }
        const k = this.size / 64; // scene units per canvas pixel
        const hUnits = this.shown.pxHeight * k;
        mesh.material.map = this.shown.texture;
        mesh.material.visible = true;
        mesh.material.needsUpdate = true;
        mesh.scale.set(this.shown.aspect * hUnits, hUnits, 1);
        mesh.position.set(this.x, this.y + hUnits / 2, 0.01); // drawn on top (renderOrder), at the characters' depth so x/y mean the same
        mesh.renderOrder = 100;
        mesh.visible = true;
        return mesh;
      }
    }

    // Deep clone with circular reference support for class instances
    function deepClone(obj, seen = new WeakMap()) {
      if (obj === null || typeof obj !== "object") return obj;

      if (seen.has(obj)) return seen.get(obj);

      let clone;
      if (Array.isArray(obj)) {
        clone = [];
        seen.set(obj, clone);
        obj.forEach((item, i) => {
          clone[i] = deepClone(item, seen);
        });
        return clone;
      }

      // Handle class instances
      clone = Object.create(Object.getPrototypeOf(obj));
      seen.set(obj, clone);

      for (let key of Reflect.ownKeys(obj)) {
        clone[key] = deepClone(obj[key], seen);
      }

      return clone;
    }

    class Scene {
      constructor(lerpTime, stayTime, backgroundColor, props) {
        this.lerpTime = lerpTime;
        this.stayTime = stayTime;
        this.backgroundColor = backgroundColor;

        let knownProps = {};
        for (let prop of props) {
          // whatever  it works
          knownProps[
            String(
              prop.name ||
                (() => {
                  prop.default = prop.default.namePrefix || "";
                  let r = prop.default + "#" + Math.random() * 10 ** 17; // for int
                  prop.name = r;
                  return r;
                })()
            )
          ] = prop;
        }
        for (let prop of props) {
          // prop.knownProps = structuredClone(knownProps);
          prop.knownProps = deepClone(knownProps);
        }
        this.props = props;
      }
      getConfig() {
        return {
          lerpTime: this.lerpTime,
          stayTime: this.stayTime,
          backgroundColor: this.backgroundColor,
          Objects: this.props.map((prop) => prop.getObjectConfig()),
        };
      }
    }

    // Public API
    return {
      Prop,
      exampleProps: {
        RotatingCubeProp,
        BouncingSphereProp,
        ImageProp,
        TextProp,
      },
      Scene,
      init(FPS, loopAtEnd, scenes, gradientMap) {
        const objectsOverTime = scenes.map((scene) => scene.getConfig());
        const renderer = CORE_3dFramesRenderer(
          FPS,
          loopAtEnd,
          objectsOverTime,
          gradientMap
        );
        renderer.init();
        return renderer;
      },
    };
  })();

  class ActionProp extends CORE_3d_PROPSsceneSYS.Prop {
    constructor(baseProp, modifier) {
      super();
      this.baseProp = baseProp;
      this.modifier = modifier || {};
    }
    getObjectConfig() {
      const config = this.baseProp.getObjectConfig();
      config.modifier.mesh = this.modifier;
      return config;
    }
  }
  // PSA_SYS function abstracts prop system with actions system
  function PSA_SYS(PSA) {
    const scenes = [];
    for (const psaScene of PSA.scenes) {
      scenes.push(
        new CORE_3d_PROPSsceneSYS.Scene(
          psaScene.lerpTime,
          psaScene.stayTimeInit,
          psaScene.backgroundColor,
          psaScene.PropsDef
        )
      );
      for (const action of psaScene.actions) {
        const modifierFunctions = action.action(psaScene.PropsDef);
        const actionProps = psaScene.PropsDef.map(
          (prop, index) => new ActionProp(prop, modifierFunctions[index])
        );
        scenes.push(
          new CORE_3d_PROPSsceneSYS.Scene(
            action.lerpTime,
            action.stayTime,
            psaScene.backgroundColor,
            actionProps
          )
        );
      }
      scenes.push(
        new CORE_3d_PROPSsceneSYS.Scene(
          0,
          psaScene.stayTimeEnd,
          psaScene.backgroundColor,
          psaScene.PropsDef
        )
      );
    }
    let rendererInstance = null;
    function init(FPS, loopAtEnd) {
      const gradientMap = PSA.defaultGredientMap || PSA.defaultGradientMap;
      rendererInstance = CORE_3d_PROPSsceneSYS.init(
        FPS,
        loopAtEnd,
        scenes,
        gradientMap
      );
      // Expose renderer controls at the edge
      return {
        instantHault: rendererInstance.instantHault,
        goToNextOOT: rendererInstance.goToNextOOT,
        instantUnhault: rendererInstance.instantUnhault,
        rendererInstance: rendererInstance,
        haulted: rendererInstance.getHault,
        init: init,
      };
    }
    return {
      init,
      getRendererInstance: () => rendererInstance,
    };
  }

  return {
    main: PSA_SYS,
    baseProp: CORE_3d_PROPSsceneSYS.Prop,
    CORE_3dFramesRenderer: CORE_3dFramesRenderer,
    CORE_3d_PROPSsceneSYS: CORE_3d_PROPSsceneSYS,
  };
  // const PSA = {
  //   defaultGredientMap: new THREE.DataTexture(
  //     new Uint8Array([255, 255, 255, 255, 255, 255, 255, 255, 255]),
  //     3,
  //     1,
  //     THREE.RGBFormat
  //   ),
  //   scenes: [
  //     {
  //       stayTimeInit: 1000,
  //       stayTimeEnd: 1000,
  //       lerpTime: 500,
  //       backgroundColor: 0x000000,
  //       PropsDef: [
  //         new CORE_3d_PROPSsceneSYS.exampleProps.RotatingCubeProp(0x00ff00, 1),
  //       ],
  //       actions: [
  //         {
  //           stayTime: 2000,
  //           lerpTime: 500,
  //           action: (PropsArr) => {
  //             // u can also call any method and hence do default stuff too
  //             // if (PropsArr[0].doAction) {
  //             //   PropsArr[0].doAction(); // after this commit are supported
  //             // }
  //             return PropsArr.map(
  //               (prop) => (mesh, totalTime, lerpProgress, step) => {
  //                 mesh.position.x = Math.sin(totalTime);
  //                 return mesh;
  //               }
  //             );
  //           },
  //         },
  //       ],
  //     },
  //   ],
  // };

  // PSA_SYS(PSA).init(60, false);
};
let ObjectAnimationSystem_INS = ObjectAnimationSystem();
