"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { type Animacion, type MascotaId, mascota } from "@/lib/mascotas";
import type { CharlaTutor } from "@/lib/useConsulta";
import { Mascota } from "./Mascota";
import { TextoEscrito } from "./TextoEscrito";
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

/** Liquid glass (globals.css .vidrio): see-through but blurred enough to read on top of the conversation. */
export const VIDRIO = "vidrio";

/** The study companion in Chat mode: the pet sits right above the composer, at the conversation's left
 *  edge; tapping it opens a bubble to ask study questions. The patient doesn't see any of it
 *  and the clock is paused while it's open. Rendered inside ChatView's composer box. */
export function TutorChat({
  mascotaId,
  charla,
  pensando,
  listo,
  onPreguntar,
  onAbierto,
}: {
  mascotaId: MascotaId;
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
  // answers already given when the bubble opened appear whole; new ones type
  const [yaEstaban, setYaEstaban] = useState(0);

  const abrir = (si: boolean) => {
    setAbierto(si);
    if (si) setYaEstaban(respuestas);
    onAbierto(si);
  };
  // switching to face to face with the bubble open: the clock must not stay paused
  const alCerrar = useRef(onAbierto);
  useEffect(() => {
    alCerrar.current = onAbierto;
  });
  useEffect(() => () => alCerrar.current(false), []);

  // braces: scrollIntoView returns a promise in recent Chrome, and an effect may only return its cleanup
  const alFinal = useCallback(() => {
    fin.current?.scrollIntoView({ block: "end" });
  }, []);
  useEffect(() => {
    alFinal();
  }, [charla.length, respuestas, alFinal]);

  const enviar = () => {
    if (!texto.trim() || pensando) return;
    onPreguntar(texto);
    setTexto("");
  };

  let n = 0; // index among the answers, to tell new ones from old ones
  return (
    <>
      {abierto && (
        <section
          aria-label={`Charla con ${nombre}`}
          onKeyDown={(e) => e.key === "Escape" && abrir(false)}
          className={`enter absolute bottom-full left-4 right-4 z-30 mb-[148px] flex max-h-[min(460px,55dvh)] origin-bottom-left flex-col rounded-3xl sm:right-auto sm:w-[380px] lg:mb-[176px] ${VIDRIO}`}
        >
          <header className="flex items-center justify-between gap-3 px-4 pb-1.5 pt-3.5">
            <p className="text-[14px] font-medium">{nombre}</p>
            <button aria-label="Cerrar" onClick={() => abrir(false)} className="press text-ink-3 hover:text-ink">
              <Close width={16} height={16} />
            </button>
          </header>
          <div className="no-scrollbar min-h-0 flex-1 overflow-y-auto px-4">
            <div className="flex flex-col gap-2 pb-3">
              {!charla.length && (
                <p className="py-1 text-[14px] leading-snug text-ink-2">
                  ¿Te trabaste? Preguntame lo que quieras: cómo seguir la anamnesis, una maniobra, una mnemotecnia, un
                  medicamento…
                </p>
              )}
              {charla.map((c, i) => {
                const nueva = c.respuesta ? n++ >= yaEstaban : false;
                return (
                  <div key={i} className="flex flex-col gap-2">
                    <p className="ml-auto max-w-[85%] rounded-[18px] rounded-br-md bg-ink px-3.5 py-2 text-[14px] leading-snug text-bg">
                      {c.pregunta}
                    </p>
                    {c.respuesta ? (
                      <p className="max-w-[90%] rounded-[18px] rounded-bl-md bg-white/[0.07] px-3.5 py-2 text-[14.5px] leading-snug text-ink">
                        <TextoEscrito texto={c.respuesta.texto} animar={nueva} alAvanzar={alFinal} />
                      </p>
                    ) : (
                      <span className="text-[13px] text-ink-3">{nombre} está buscando en los apuntes…</span>
                    )}
                  </div>
                );
              })}
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
              className="min-w-0 flex-1 bg-transparent text-[15px] outline-none placeholder:text-ink-3"
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
        className="press absolute bottom-full left-3 z-20 mb-11 rounded-2xl p-1"
      >
        <span className="lg:hidden">
          <Mascota id={mascotaId} animacion={animacion} alto={88} />
        </span>
        <span className="hidden lg:block">
          <Mascota id={mascotaId} animacion={animacion} alto={116} />
        </span>
      </button>
    </>
  );
}
