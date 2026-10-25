"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

// Voice for face-to-face mode. Speech to text runs in the browser (Web Speech API: free, no quota);
// the patient's voice comes from the backend (/api/sessions/{id}/voz, Gemini TTS).

// The Web Speech API isn't in TypeScript's DOM types yet: the minimal surface we use.
type Reconocimiento = {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult:
    | ((e: {
        resultIndex: number;
        results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }>;
      }) => void)
    | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
};

function crearReconocimiento(): Reconocimiento | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as Record<string, (new () => Reconocimiento) | undefined>;
  const Ctor = w.SpeechRecognition ?? w.webkitSpeechRecognition;
  return Ctor ? new Ctor() : null;
}

/** Normalized words, to compare what was heard with what the patient is saying. */
export function palabras(t: string) {
  return t
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .split(/[^a-z0-9ñ]+/)
    .filter((w) => w.length > 2);
}

type Escucha = {
  /** A finished phrase (the browser detected the pause at the end of it). */
  onFrase: (texto: string) => void;
  /** The student started talking: used to interrupt the patient. */
  onVoz: (texto: string) => void;
  /** True if what was heard is the patient's own voice coming back through the speakers. */
  esEco: (texto: string) => boolean;
};

/** Hands-free listening for the call: one phrase at a time, restarting after each, until colgar(). */
export function useEscucha({ onFrase, onVoz, esEco }: Escucha) {
  const [soportado, setSoportado] = useState(false);
  const [activa, setActiva] = useState(false);
  const [parcial, setParcial] = useState("");
  const enLlamada = useRef(false);
  const rec = useRef<Reconocimiento | null>(null);
  const cb = useRef({ onFrase, onVoz, esEco });
  useEffect(() => {
    cb.current = { onFrase, onVoz, esEco };
  });

  useEffect(() => {
    // feature detection needs window, so it runs after hydration
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setSoportado(!!crearReconocimiento());
    return () => {
      enLlamada.current = false;
      rec.current?.abort();
    };
  }, []);

  // one phrase per recognition session; it restarts itself while the call is on (created once)
  const [escuchar] = useState(() => {
    const escuchar = () => {
      if (!enLlamada.current) return;
      const r = crearReconocimiento();
      if (!r) return;
      rec.current = r;
      r.lang = "es-UY";
      r.interimResults = true;
      r.continuous = false; // ends by itself at the pause after a phrase: that's the turn-taking
      const inicio = Date.now();
      let final = "";
      r.onresult = (e) => {
        let interino = "";
        for (let i = e.resultIndex; i < e.results.length; i++) {
          const res = e.results[i];
          if (res.isFinal) final += res[0].transcript;
          else interino += res[0].transcript;
        }
        const t = (final + interino).trim();
        if (!t || cb.current.esEco(t)) return;
        setParcial(t);
        cb.current.onVoz(t);
      };
      r.onerror = (e) => {
        if (["not-allowed", "service-not-allowed", "audio-capture"].includes(e.error)) {
          enLlamada.current = false;
          setActiva(false);
          toast.error("Para hablarle al paciente, permití el micrófono en el navegador.", { id: "mic" });
        }
      };
      r.onend = () => {
        setParcial("");
        const t = final.trim();
        if (t && !cb.current.esEco(t)) cb.current.onFrase(t);
        // listen again; if it ended right away (silence timeout, a hiccup) don't spin in a tight loop
        if (enLlamada.current) setTimeout(escuchar, Date.now() - inicio < 400 ? 600 : 0);
      };
      try {
        r.start();
      } catch {
        setTimeout(escuchar, 600);
      }
    };
    return escuchar;
  });

  const contestar = useCallback(() => {
    if (enLlamada.current) return;
    enLlamada.current = true;
    setActiva(true);
    escuchar();
  }, [escuchar]);

  const colgar = useCallback(() => {
    enLlamada.current = false;
    setActiva(false);
    setParcial("");
    rec.current?.abort();
  }, []);

  return { soportado, activa, parcial, contestar, colgar };
}

/** Plays the patient's audio through one AudioContext, with an analyser the avatar can read for lip-sync. */
export function useVozPaciente() {
  const ctx = useRef<AudioContext | null>(null);
  const analyser = useRef<AnalyserNode | null>(null);
  const fuente = useRef<AudioBufferSourceNode | null>(null);
  const [hablando, setHablando] = useState(false);

  /** Creates or resumes the AudioContext. Call it from a tap or key press: iOS only allows audio after a gesture. */
  const desbloquear = useCallback(() => {
    if (!ctx.current) {
      const C =
        window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      ctx.current = new C();
      analyser.current = ctx.current.createAnalyser();
      analyser.current.fftSize = 1024;
      analyser.current.connect(ctx.current.destination);
    }
    if (ctx.current.state === "suspended") void ctx.current.resume();
  }, []);

  const callar = useCallback(() => {
    fuente.current?.stop();
    fuente.current = null;
    setHablando(false);
  }, []);

  const reproducir = useCallback(
    async (wav: ArrayBuffer) => {
      desbloquear();
      const c = ctx.current!;
      const buffer = await c.decodeAudioData(wav);
      callar();
      const src = c.createBufferSource();
      src.buffer = buffer;
      src.connect(analyser.current!);
      src.onended = () => {
        if (fuente.current === src) {
          fuente.current = null;
          setHablando(false);
        }
      };
      fuente.current = src;
      setHablando(true);
      src.start();
    },
    [desbloquear, callar],
  );

  useEffect(() => () => void ctx.current?.close(), []);

  return { hablando, analyser, desbloquear, reproducir, callar };
}
