"use client";

import { VRMLoaderPlugin, VRMUtils, type VRM } from "@pixiv/three-vrm";
import { useEffect, useRef, type RefObject } from "react";
import {
  AmbientLight,
  DirectionalLight,
  Object3D,
  PerspectiveCamera,
  Scene,
  SRGBColorSpace,
  Vector3,
  WebGLRenderer,
} from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

// The patient as a VRM avatar (three.js + three-vrm): idle motion made in code (breathing, sway, blinks,
// eye contact with small saccades) and a mouth driven by the voice already playing through the call's
// AnalyserNode. Loaded only in face-to-face mode (next/dynamic); FaceView keeps the ASCII portrait until
// it is ready and if WebGL fails. Kept cheap for phones: 30 fps, pixel ratio <= 1.5, head-and-shoulders.

const FPS = 30;
const tau = Math.PI * 2;

type Props = {
  url: string;
  /** The patient's voice (useVozPaciente): its waveform moves the mouth. */
  analyser: RefObject<AnalyserNode | null>;
  hablando: boolean;
  onListo: () => void;
  onError: () => void;
  className?: string;
};

export default function Avatar3D({ url, analyser, hablando, onListo, onError, className }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const estado = useRef({ hablando, onListo, onError });
  useEffect(() => {
    estado.current = { hablando, onListo, onError };
  });

  useEffect(() => {
    const canvas = canvasRef.current!;
    let renderer: WebGLRenderer;
    try {
      renderer = new WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: "low-power" });
    } catch {
      estado.current.onError(); // no WebGL: the ASCII portrait stays
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    renderer.outputColorSpace = SRGBColorSpace;

    const scene = new Scene();
    const camera = new PerspectiveCamera(20, 1, 0.1, 20); // narrow lens: a portrait, little distortion
    scene.add(camera);
    const luz = new DirectionalLight(0xffffff, Math.PI * 0.9);
    luz.position.set(0.6, 1, 1.4).normalize();
    scene.add(luz, new AmbientLight(0xffffff, 0.5));
    const mirada = new Object3D(); // where the eyes look: the camera, plus small saccades
    camera.add(mirada);

    const ajustar = () => {
      const { clientWidth: w, clientHeight: h } = canvas.parentElement!;
      if (!w || !h) return;
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    };
    const ro = new ResizeObserver(ajustar);
    ro.observe(canvas.parentElement!);
    ajustar();

    let vrm: VRM | null = null;
    let cancelado = false;
    const loader = new GLTFLoader();
    loader.register((parser) => new VRMLoaderPlugin(parser));
    loader
      .loadAsync(url)
      .then((gltf) => {
        if (cancelado) return;
        vrm = gltf.userData.vrm as VRM;
        VRMUtils.removeUnnecessaryVertices(gltf.scene);
        VRMUtils.combineSkeletons(gltf.scene);
        if (vrm.meta.metaVersion === "0") VRMUtils.rotateVRM0(vrm);
        vrm.scene.traverse((o) => (o.frustumCulled = false));
        scene.add(vrm.scene);

        // arms down from the T-pose (they'd stick out at the edges of the frame)
        const brazo = (lado: "left" | "right", z: number) => {
          const b = vrm!.humanoid.getNormalizedBoneNode(`${lado}UpperArm`);
          if (b) b.rotation.z = z;
        };
        brazo("left", -1.2);
        brazo("right", 1.2);

        // head-and-shoulders framing, from where this model's head actually is
        vrm.scene.updateMatrixWorld(true);
        const cabeza = new Vector3();
        vrm.humanoid.getNormalizedBoneNode("head")?.getWorldPosition(cabeza);
        camera.position.set(0, cabeza.y - 0.02, cabeza.z + 1.9);
        camera.lookAt(0, cabeza.y - 0.1, cabeza.z);
        if (vrm.lookAt) vrm.lookAt.target = mirada;
        estado.current.onListo();
      })
      .catch(() => !cancelado && estado.current.onError());

    // --- idle motion -----------------------------------------------------------------------------
    const calmo = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0.3 : 1;
    const onda = new Float32Array(1024);
    let boca = 0; // smoothed loudness, 0..1
    let vocal = 0.5; // smoothed brightness of the sound: open "o/u" (low) .. "e/i" (high)
    let proximoParpadeo = 2;
    let parpadeo = -1; // seconds since the blink started, -1 = eyes open
    let proximaSacada = 1;

    const actualizar = (dt: number, t: number) => {
      if (!vrm) return;
      const h = vrm.humanoid;
      const hueso = (n: Parameters<typeof h.getNormalizedBoneNode>[0]) => h.getNormalizedBoneNode(n);

      // mouth: RMS of what is playing right now, with a fast attack and a slower release
      let objetivo = 0;
      let cruces = 0;
      const a = analyser.current;
      if (a && estado.current.hablando) {
        a.getFloatTimeDomainData(onda);
        let suma = 0;
        for (let i = 0; i < onda.length; i++) {
          suma += onda[i] * onda[i];
          if (i && onda[i - 1] < 0 !== onda[i] < 0) cruces++;
        }
        objetivo = Math.min(1, Math.max(0, (Math.sqrt(suma / onda.length) - 0.012) * 9));
      }
      boca += (objetivo - boca) * (objetivo > boca ? 0.55 : 0.25);
      if (objetivo > 0.05) vocal += (Math.min(1, cruces / 120) - vocal) * 0.2;
      const e = vrm.expressionManager;
      if (e) {
        // the loudness opens the mouth; how "bright" the sound is picks between a, o/u and e/i shapes
        e.setValue("aa", boca * (1 - Math.abs(vocal - 0.5)) * 0.9);
        e.setValue("oh", boca * Math.max(0, 0.5 - vocal) * 1.2);
        e.setValue("ih", boca * Math.max(0, vocal - 0.5) * 1.1);

        // blinks every 2-6 s, sometimes twice
        proximoParpadeo -= dt;
        if (proximoParpadeo <= 0 && parpadeo < 0) {
          parpadeo = 0;
          proximoParpadeo = Math.random() < 0.15 ? 0.25 : 2 + Math.random() * 4;
        }
        if (parpadeo >= 0) {
          parpadeo += dt;
          const d = 0.16;
          e.setValue("blink", parpadeo < d ? Math.sin((parpadeo / d) * Math.PI) : 0);
          if (parpadeo >= d) parpadeo = -1;
        }
      }

      // breathing and a slow, never-repeating sway (sums of sines at unrelated frequencies)
      const respiro = Math.sin((tau * t) / 4.5);
      const columna = hueso("spine");
      if (columna) columna.rotation.x = 0.012 * respiro * calmo;
      const pecho = hueso("chest");
      if (pecho) pecho.rotation.x = 0.01 * respiro * calmo;
      const cuello = hueso("neck");
      if (cuello) {
        cuello.rotation.y = (0.035 * Math.sin(t * 0.47) + 0.015 * Math.sin(t * 1.31)) * calmo;
        cuello.rotation.x = (0.02 * Math.sin(t * 0.61 + 1) + boca * 0.03) * calmo; // small nods while talking
      }
      const cabeza = hueso("head");
      if (cabeza) cabeza.rotation.z = (0.025 * Math.sin(t * 0.37 + 2) + 0.01 * Math.sin(t * 1.07)) * calmo;

      // eye contact with micro-saccades
      proximaSacada -= dt;
      if (proximaSacada <= 0) {
        proximaSacada = 1 + Math.random() * 2.5;
        mirada.position.set((Math.random() - 0.5) * 0.08, (Math.random() - 0.5) * 0.05, 0);
      }

      vrm.update(dt);
    };

    let raf = 0;
    let anterior = performance.now();
    const cuadro = (ahora: number) => {
      raf = requestAnimationFrame(cuadro);
      if (ahora - anterior < 1000 / FPS - 1) return; // 30 fps is plenty for a portrait and saves battery
      const dt = Math.min((ahora - anterior) / 1000, 0.1);
      anterior = ahora;
      actualizar(dt, ahora / 1000);
      renderer.render(scene, camera);
    };
    raf = requestAnimationFrame(cuadro); // browsers pause it in hidden tabs

    return () => {
      cancelado = true;
      cancelAnimationFrame(raf);
      ro.disconnect();
      if (vrm) VRMUtils.deepDispose(vrm.scene);
      renderer.dispose();
      renderer.forceContextLoss();
    };
  }, [url, analyser]);

  return <canvas ref={canvasRef} className={className} />;
}
