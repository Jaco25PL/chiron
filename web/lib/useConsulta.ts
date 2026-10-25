"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { api, type Caso, type Resumen, type Turno } from "./api";

export const DURACION_S = 7 * 60;

/** Estado de una consulta: sesión en el backend, transcripción, temporizador y cierre. */
export function useConsulta(caseId: string) {
  const [caso, setCaso] = useState<Caso | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [turnos, setTurnos] = useState<Turno[]>([]);
  const [pensando, setPensando] = useState(false);
  const [inicio, setInicio] = useState<number | null>(null);
  const [resumen, setResumen] = useState<Resumen | null>(null);
  const creada = useRef(false);

  useEffect(() => {
    if (creada.current) return; // en desarrollo React monta dos veces: una sola sesión
    creada.current = true;
    api.casos().then((cs) => setCaso(cs.find((c) => c.id === caseId) ?? null)).catch(() => {});
    api
      .nuevaSesion(caseId)
      .then((r) => setSessionId(r.session_id))
      .catch((e: Error) => toast.error(e.message));
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

/** Segundos restantes de los 7 minutos (negativo si se pasó). Pausa el render cuando la pestaña está oculta. */
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
