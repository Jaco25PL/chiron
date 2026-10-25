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
  onresult: ((e: { resultIndex: number; results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }) => void) | null;
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

/** Push-to-talk dictation: start() listens until the student stops talking, then calls onFinal. */
export function useDictado(onFinal: (texto: string) => void) {
  const [soportado, setSoportado] = useState(false);
  const [escuchando, setEscuchando] = useState(false);
  const [parcial, setParcial] = useState("");
  const rec = useRef<Reconocimiento | null>(null);
  const alTerminar = useRef(onFinal);
  useEffect(() => {
    alTerminar.current = onFinal;
  }, [onFinal]);

  useEffect(() => {
    // feature detection needs window, so it runs after hydration
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setSoportado(!!crearReconocimiento());
    return () => rec.current?.abort();
  }, []);

  const empezar = useCallback(() => {
    const r = crearReconocimiento();
    if (!r) return;
    rec.current?.abort();
    rec.current = r;
    r.lang = "es-UY";
    r.interimResults = true;
    r.continuous = false; // ends on its own after a pause
    let final = "";
    r.onresult = (e) => {
      let interino = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const res = e.results[i];
        if (res.isFinal) final += res[0].transcript;
        else interino += res[0].transcript;
      }
      setParcial((final + interino).trim());
    };
    r.onerror = (e) => {
      if (e.error === "not-allowed" || e.error === "service-not-allowed") {
        setParcial("");
        toast.error("Para hablarle al paciente, permití el micrófono en el navegador.", { id: "mic" });
      }
    };
    r.onend = () => {
      setEscuchando(false);
      setParcial("");
      if (final.trim()) alTerminar.current(final.trim());
    };
    setParcial("");
    setEscuchando(true);
    r.start();
  }, []);

  const parar = useCallback(() => rec.current?.stop(), []);

  return { soportado, escuchando, parcial, empezar, parar };
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
      const C = window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
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
