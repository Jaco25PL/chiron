"use client";

import { useEffect, useRef, useState } from "react";
import type { Nivel } from "@/lib/api";
import { type Animacion, type MascotaId, mascota } from "@/lib/mascotas";
import type { CharlaTutor } from "@/lib/useConsulta";
import { Mascota } from "./Mascota";
import { Close } from "./icons";

/** What the pet does: thinks while the answer comes, greets when it arrives, waits while open. */
export function useAnimacionTutor(abierto: boolean, pensando: boolean, respuestas: number): Animacion {
  const [saludando, setSaludando] = useState(false);
  const vistas = useRef(respuestas);
  useEffect(() => {
    if (respuestas <= vistas.current) return;
    vistas.current = respuestas;
    const on = setTimeout(() => setSaludando(true), 0);
    const off = setTimeout(() => setSaludando(false), 2800);
    return () => {
      clearTimeout(on);
      clearTimeout(off);
    };
  }, [respuestas]);
  if (pensando) return "revisando";
  if (saludando) return "saludo";
  return abierto ? "esperando" : "reposo";
}

/** "Te doy la respuesta" / "te doy pistas": how the companion helps at each level. */
export function ayudaTutor(nivel: Nivel) {
  return nivel === "principiante" ? "te ayuda con la respuesta" : "te da pistas, no la respuesta";
}

/** The study companion in Chat mode: the pet floats in a corner; tapping it opens a bubble to ask it
 *  study questions. The patient doesn't see any of it and the clock is paused while it's open. */
export function TutorChat({
  mascotaId,
  nivel,
  charla,
  pensando,
  listo,
  onPreguntar,
  onAbierto,
}: {
  mascotaId: MascotaId;
  nivel: Nivel;
  charla: CharlaTutor[];
  pensando: boolean;
  listo: boolean;
  onPreguntar: (texto: string) => void;
  onAbierto: (abierto: boolean) => void;
}) {
  const [abierto, setAbierto] = useState(false);
  const [texto, setTexto] = useState("");
  const fin = useRef<HTMLDivElement>(null);
  const nombre = mascota(mascotaId).nombre;
  const respuestas = charla.filter((c) => c.respuesta).length;
  const animacion = useAnimacionTutor(abierto, pensando, respuestas);

  const abrir = (si: boolean) => {
    setAbierto(si);
    onAbierto(si);
  };
  // switching to face to face with the bubble open: the clock must not stay paused
  const alCerrar = useRef(onAbierto);
  useEffect(() => {
    alCerrar.current = onAbierto;
  });
  useEffect(() => () => alCerrar.current(false), []);
  useEffect(() => {
    fin.current?.scrollIntoView({ block: "end" });
  }, [charla.length, respuestas]);

  const enviar = () => {
    if (!texto.trim() || pensando) return;
    onPreguntar(texto);
    setTexto("");
  };

  return (
    <div className="fixed bottom-[calc(max(16px,env(safe-area-inset-bottom))+104px)] left-3 z-30 flex flex-col items-start gap-2 sm:left-6">
      {abierto && (
        <section
          aria-label={`Charla con ${nombre}`}
          onKeyDown={(e) => e.key === "Escape" && abrir(false)}
          className="glass enter flex max-h-[min(460px,60dvh)] w-[min(360px,calc(100vw-24px))] origin-bottom-left flex-col rounded-3xl bg-bg-2/85"
        >
          <header className="flex items-start justify-between gap-3 px-4 pb-2 pt-3.5">
            <div>
              <p className="text-[14px] font-medium">{nombre}</p>
              <p className="text-[12px] text-ink-3">
                Tu compañera de estudio {ayudaTutor(nivel)} · el reloj está en pausa
              </p>
            </div>
            <button aria-label="Cerrar" onClick={() => abrir(false)} className="press text-ink-3 hover:text-ink">
              <Close width={16} height={16} />
            </button>
          </header>
          <div className="min-h-0 flex-1 overflow-y-auto px-4">
            <div className="flex flex-col gap-2 pb-2">
              {!charla.length && (
                <p className="py-2 text-[13.5px] text-ink-2">
                  ¿Te trabaste? Preguntame lo que quieras: cómo seguir la anamnesis, una maniobra, una mnemotecnia, un
                  medicamento… El paciente no se entera.
                </p>
              )}
              {charla.map((c, i) => (
                <div key={i} className="flex flex-col gap-2">
                  <p className="ml-auto max-w-[85%] rounded-[18px] rounded-br-md bg-ink px-3.5 py-2 text-[14px] leading-snug text-bg">
                    {c.pregunta}
                  </p>
                  {c.respuesta ? (
                    <p className="enter max-w-[90%] rounded-[18px] rounded-bl-md bg-accent/[0.12] px-3.5 py-2 text-[14px] leading-snug text-ink">
                      {c.respuesta.texto}
                    </p>
                  ) : (
                    <span className="text-[13px] text-ink-3">{nombre} está buscando en los apuntes…</span>
                  )}
                </div>
              ))}
              <div ref={fin} />
            </div>
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              enviar();
            }}
            className="flex items-center gap-2 border-t border-line px-3 py-2.5"
          >
            <input
              autoFocus
              value={texto}
              onChange={(e) => setTexto(e.target.value)}
              maxLength={1000}
              placeholder={`Preguntale a ${nombre}…`}
              aria-label={`Pregunta para ${nombre}`}
              className="min-w-0 flex-1 bg-transparent text-[14.5px] outline-none placeholder:text-ink-3"
            />
            <button
              type="submit"
              disabled={!texto.trim() || pensando || !listo}
              className="press h-8 rounded-full bg-accent px-3.5 text-[13px] font-medium text-accent-ink disabled:opacity-40"
            >
              Preguntar
            </button>
          </form>
        </section>
      )}
      <button
        type="button"
        onClick={() => abrir(!abierto)}
        aria-expanded={abierto}
        aria-label={abierto ? `Cerrar la charla con ${nombre}` : `Preguntarle a ${nombre}, tu compañera de estudio`}
        title={abierto ? undefined : `¿Dudas? Preguntale a ${nombre}`}
        className="press rounded-2xl p-1"
      >
        <Mascota id={mascotaId} animacion={animacion} alto={76} />
      </button>
    </div>
  );
}
