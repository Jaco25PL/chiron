"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { api, type Caso, type Resumen, type Turno } from "./api";

export const DURACION_S = 7 * 60;

/** Consultation state: backend session, transcript, timer and closing. */
export function useConsulta(caseId: string) {
  const [caso, setCaso] = useState<Caso | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [turnos, setTurnos] = useState<Turno[]>([]);
  const [pensando, setPensando] = useState(false);
  const [inicio, setInicio] = useState<number | null>(null);
  const [resumen, setResumen] = useState<Resumen | null>(null);
  const creada = useRef(false);

  useEffect(() => {
    if (creada.current) return; // React mounts twice in dev: create a single session
    creada.current = true;
    api.casos().then((cs) => setCaso(cs.find((c) => c.id === caseId) ?? null)).catch(() => {});
    api
      .nuevaSesion(caseId)
      .then((r) => setSessionId(r.session_id))
      .catch((e: Error) => toast.error(e.message, { id: "sesion" }));
  }, [caseId]);

  const enviar = useCallback(
    async (texto: string) => {
      const text = texto.trim();
      if (!text || !sessionId || pensando) return;
      setInicio((t) => t ?? Date.now());
      setTurnos((ts) => [...ts, { role: "estudiante", text }]);
      setPensando(true);
      try {
        const r = await api.enviar(sessionId, text);
        setTurnos((ts) => [...ts, ...r.replies]);
      } catch (e) {
        toast.error((e as Error).message);
      } finally {
        setPensando(false);
      }
    },
    [sessionId, pensando],
  );

  const terminar = useCallback(async () => {
    if (!sessionId) return;
    try {
      setResumen(await api.terminar(sessionId));
    } catch (e) {
      toast.error((e as Error).message);
    }
  }, [sessionId]);

  return { caso, listo: !!sessionId, turnos, pensando, inicio, enviar, terminar, resumen, setResumen };
}

/** Seconds left of the 7 minutes (negative once over). Skips re-renders while the tab is hidden. */
export function useCuentaRegresiva(inicio: number | null) {
  const [ahora, setAhora] = useState(() => Date.now());
  useEffect(() => {
    if (inicio === null) return;
    const id = setInterval(() => {
      if (!document.hidden) setAhora(Date.now());
    }, 500);
    return () => clearInterval(id);
  }, [inicio]);
  return inicio === null ? DURACION_S : DURACION_S - Math.floor((ahora - inicio) / 1000);
}

export function formatoTiempo(s: number) {
  const neg = s < 0;
  const a = Math.abs(s);
  return `${neg ? "−" : ""}${Math.floor(a / 60)}:${String(a % 60).padStart(2, "0")}`;
}
