"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { api, type Caso, type ItemChecklist, type Nivel, type Resumen, type RespuestaTutor, type Turno } from "./api";

/** How the face-to-face call hears back: the reply's text, then the patient's voice in chunks. */
export type ConVoz = {
  alResponder: (replies: Turno[]) => void;
  alAudio: (pcm: ArrayBuffer) => void;
  alTerminar: () => void;
};

/** The same for the study companion: its answer's text, then its voice. */
export type ConVozTutor = {
  alResponder: (r: RespuestaTutor) => void;
  alAudio: (pcm: ArrayBuffer) => void;
  alTerminar: () => void;
};

/** A question to the study companion and its answer (null while it thinks). */
export type CharlaTutor = { pregunta: string; respuesta: RespuestaTutor | null };

/** Time the station's clock was paused (the student talking to the study companion). */
type Pausa = { total: number; desde: number | null };

export const DURACION_S = 7 * 60;

/** Consultation state: backend session, transcript, timer and closing. In "principiante" also the
 *  checklist, as the backend ticked it in its latest response (null in "normal"). */
export function useConsulta(caseId: string, modo: "chat" | "cara" = "chat", nivel: Nivel = "normal") {
  const [caso, setCaso] = useState<Caso | null>(null);
  const [checklist, setChecklist] = useState<ItemChecklist[] | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [turnos, setTurnos] = useState<Turno[]>([]);
  const [pensando, setPensando] = useState(false);
  const [inicio, setInicio] = useState<number | null>(null);
  const [resumen, setResumen] = useState<Resumen | null>(null);
  const [corrigiendo, setCorrigiendo] = useState(false); // the docente is grading the consultation
  const [tutor, setTutor] = useState<CharlaTutor[]>([]);
  const [pausa, setPausa] = useState<Pausa>({ total: 0, desde: null });
  const creada = useRef(false);

  useEffect(() => {
    if (creada.current) return; // React mounts twice in dev: create a single session
    creada.current = true;
    // the backend tells us who the patient is (also for "aleatorio", picked on the server)
    api
      .nuevaSesion(caseId, modo, nivel)
      .then((r) => {
        setCaso(r.case);
        setSessionId(r.session_id);
        if (r.checklist) setChecklist(r.checklist);
      })
      .catch((e: Error) => toast.error(e.message, { id: "sesion" }));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- created once, with the mode and level the user opened it in
  }, [caseId]);

  const enviar = useCallback(
    async (texto: string, voz?: ConVoz) => {
      const text = texto.trim();
      if (!text || !sessionId || pensando) return;
      setInicio((t) => t ?? Date.now());
      setTurnos((ts) => [...ts, { role: "estudiante", text }]);
      setPensando(true);
      let respondio = false;
      try {
        if (voz) {
          await api.enviarConVoz(sessionId, text, {
            onRespuesta: (r) => {
              respondio = true;
              setTurnos((ts) => [...ts, ...r.replies]);
              if (r.checklist) setChecklist(r.checklist);
              setPensando(false); // the student may talk again while the patient's voice is still arriving
              voz.alResponder(r.replies);
            },
            onAudio: voz.alAudio,
          });
        } else {
          const r = await api.enviar(sessionId, text);
          setTurnos((ts) => [...ts, ...r.replies]);
          if (r.checklist) setChecklist(r.checklist);
        }
      } catch (e) {
        if (!respondio) toast.error((e as Error).message);
        else toast.error("No se pudo reproducir la voz del paciente; seguí con los subtítulos.", { id: "voz" });
      } finally {
        voz?.alTerminar();
        setPensando(false);
      }
    },
    [sessionId, pensando],
  );

  /** Stops or restarts the clock: while the student talks to the study companion, no time runs. */
  const pausar = useCallback(
    (si: boolean) => {
      setPausa((p) => {
        const ahora = Date.now();
        if (si && p.desde === null) return { ...p, desde: ahora };
        if (!si && p.desde !== null) {
          // only the part after the consultation started was on the clock
          const desde = Math.max(p.desde, inicio ?? ahora);
          return { total: p.total + Math.max(0, ahora - desde), desde: null };
        }
        return p;
      });
    },
    [inicio],
  );

  const tutorPensando = tutor.some((c) => !c.respuesta);
  /** A question to the study companion. With `voz`, it answers out loud. */
  const preguntarTutor = useCallback(
    async (texto: string, voz?: ConVozTutor) => {
      const pregunta = texto.trim();
      if (!pregunta || !sessionId || tutorPensando) return;
      setTutor((cs) => [...cs, { pregunta, respuesta: null }]);
      const responder = (r: RespuestaTutor) =>
        setTutor((cs) => cs.map((c, i) => (i === cs.length - 1 ? { ...c, respuesta: r } : c)));
      let respondio = false;
      try {
        if (voz) {
          await api.tutorConVoz(sessionId, pregunta, {
            onRespuesta: (r) => {
              respondio = true;
              responder(r);
              voz.alResponder(r);
            },
            onAudio: voz.alAudio,
          });
        } else {
          responder(await api.tutor(sessionId, pregunta));
          respondio = true;
        }
      } catch (e) {
        if (!respondio) {
          setTutor((cs) => cs.slice(0, -1)); // the question had no answer: let it be asked again
          toast.error((e as Error).message, { id: "tutor" });
        }
      } finally {
        voz?.alTerminar();
      }
    },
    [sessionId, tutorPensando],
  );

  const terminar = useCallback(async () => {
    if (!sessionId || corrigiendo) return;
    setCorrigiendo(true);
    try {
      setResumen(await api.terminar(sessionId));
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setCorrigiendo(false);
    }
  }, [sessionId, corrigiendo]);

  const listo = !!sessionId;
  // waiting long enough to look stuck: usually the backend cold-starting (Cloud Run scales to zero)
  const demora = useDemora(!listo || pensando);
  return {
    caso,
    sessionId,
    listo,
    turnos,
    pensando,
    demora,
    inicio,
    enviar,
    terminar,
    corrigiendo,
    resumen,
    setResumen,
    checklist,
    tutor,
    tutorPensando,
    preguntarTutor,
    pausa,
    pausar,
  };
}

/** Seconds left of the 7 minutes (negative once over), not counting the paused time. Skips re-renders
 *  while the tab is hidden or the clock is paused. */
export function useCuentaRegresiva(inicio: number | null, pausa: Pausa = { total: 0, desde: null }) {
  const [ahora, setAhora] = useState(() => Date.now());
  useEffect(() => {
    if (inicio === null) return;
    const id = setInterval(() => {
      if (!document.hidden) setAhora(Date.now());
    }, 500);
    return () => clearInterval(id);
  }, [inicio]);
  if (inicio === null) return DURACION_S;
  // paused before the consultation started: that time was never on the clock
  const pausado = pausa.total + (pausa.desde !== null ? ahora - Math.max(pausa.desde, inicio) : 0);
  return DURACION_S - Math.floor(Math.max(0, ahora - inicio - pausado) / 1000);
}

export function formatoTiempo(s: number) {
  const neg = s < 0;
  const a = Math.abs(s);
  return `${neg ? "−" : ""}${Math.floor(a / 60)}:${String(a % 60).padStart(2, "0")}`;
}

/** True once `activo` has stayed true for `ms`; resets as soon as it turns false. */
export function useDemora(activo: boolean, ms = 3500) {
  const [demora, setDemora] = useState(false);
  useEffect(() => {
    if (!activo) return;
    const id = setTimeout(() => setDemora(true), ms);
    return () => {
      clearTimeout(id);
      setDemora(false); // reset when the wait ends (cleanup, not the effect body)
    };
  }, [activo, ms]);
  return activo && demora;
}
