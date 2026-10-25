"use client";

import { useEffect, useState } from "react";
import type { Caso, Turno } from "@/lib/api";
import { ASCII_FACE } from "@/lib/ascii-face";
import { Composer } from "./Composer";
import { CameraOff, Close, Mic, PhoneDown, Stethoscope } from "./icons";

/** Retrato ASCII del caso: public/retratos/<id>.txt, si no default.txt, si no el busto generado. */
function useRetrato(caseId: string | undefined) {
  const [arte, setArte] = useState(ASCII_FACE);
  useEffect(() => {
    if (!caseId) return;
    const leer = (f: string) => fetch(`/retratos/${f}.txt`).then((r) => (r.ok ? r.text() : null));
    leer(caseId)
      .then((t) => t ?? leer("default"))
      .then((t) => t && setArte(t.replace(/\s+$/, "")))
      .catch(() => {});
  }, [caseId]);
  const lineas = arte.split("\n");
  const cols = Math.max(...lineas.map((l) => l.length));
  return { arte, cols, filas: lineas.length };
}

/** Vista "cara a cara": una videollamada con el paciente. Por ahora el rostro es un retrato ASCII fijo. */
export function FaceView({
  caso,
  turnos,
  pensando,
  listo,
  onSend,
  onEnd,
}: {
  caso: Caso | null;
  turnos: Turno[];
  pensando: boolean;
  listo: boolean;
  onSend: (t: string) => void;
  onEnd: () => void;
}) {
  const ultimoPaciente = [...turnos].reverse().find((t) => t.role === "paciente");
  const ultimoIdx = turnos.length - 1;
  const ultimoDocente = turnos[ultimoIdx]?.role === "docente" ? turnos[ultimoIdx] : null;
  const [cerrado, setCerrado] = useState<number | null>(null);
  const nombre = caso?.paciente.nombre.split(" ").slice(0, 2).join(" ") ?? "Paciente";
  const { arte, cols, filas } = useRetrato(caso?.id);

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 px-3 pb-[max(12px,env(safe-area-inset-bottom))] sm:px-6">
      {/* escenario */}
      <div className="relative min-h-0 flex-1 overflow-hidden rounded-[28px] border border-line bg-[radial-gradient(ellipse_at_50%_35%,#0f1716_0%,#050607_70%)] [container-type:size]">
        <pre
          aria-label={`Retrato de ${nombre}`}
          className="pointer-events-none absolute left-1/2 top-[52%] -translate-x-1/2 -translate-y-1/2 select-none font-mono leading-none [mask-image:radial-gradient(ellipse_70%_75%_at_50%_45%,#000_55%,transparent_100%)]"
          style={{
            // un carácter monoespaciado mide ~0.6em de ancho. Manda la altura; en pantallas angostas
            // (mobile) se deja que los hombros se salgan por los costados para que la cara se vea grande
            fontSize: `min(calc(150cqw / ${cols * 0.6}), calc(90cqh / ${filas}))`,
            backgroundImage: "linear-gradient(180deg,#eafffb 0%,#6ee7d2 45%,#2b8c7e 100%)",
            WebkitBackgroundClip: "text",
            backgroundClip: "text",
            color: "transparent",
          }}
        >
          {arte}
        </pre>
        {/* líneas de barrido fijas */}
        <div className="pointer-events-none absolute inset-0 bg-[repeating-linear-gradient(0deg,rgb(0_0_0/0.18)_0px,rgb(0_0_0/0.18)_1px,transparent_1px,transparent_3px)]" />

        {/* propia cámara */}
        <div className="glass absolute right-3 top-3 grid aspect-[3/4] w-[22%] max-w-36 min-w-20 place-items-center rounded-2xl sm:right-4 sm:top-4">
          <div className="flex flex-col items-center gap-1.5 text-ink-3">
            <CameraOff width={18} height={18} />
            <span className="text-[11px]">Vos</span>
          </div>
        </div>

        {/* nombre */}
        <div className="glass absolute left-3 top-3 flex items-center gap-2 rounded-full py-1.5 pl-2.5 pr-3.5 sm:left-4 sm:top-4">
          <span className="size-2 rounded-full bg-live shadow-[0_0_10px_var(--live)]" />
          <span className="text-[13px] font-medium">{nombre}</span>
          {caso && <span className="text-[13px] text-ink-3">{caso.paciente.edad}</span>}
        </div>

        {/* informe del docente */}
        {ultimoDocente && cerrado !== ultimoIdx && (
          <div
            key={ultimoIdx}
            className="glass enter absolute inset-x-3 top-16 max-h-[45%] overflow-y-auto rounded-2xl p-4 sm:inset-x-auto sm:left-4 sm:top-16 sm:max-w-sm"
          >
            <div className="mb-2 flex items-center justify-between">
              <span className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-[0.14em] text-accent">
                <Stethoscope width={14} height={14} /> Docente
              </span>
              <button aria-label="Cerrar informe" onClick={() => setCerrado(ultimoIdx)} className="press text-ink-3 hover:text-ink">
                <Close width={16} height={16} />
              </button>
            </div>
            <p className="whitespace-pre-wrap font-mono text-[12.5px] leading-relaxed">{ultimoDocente.text}</p>
          </div>
        )}

        {/* subtítulos */}
        <div className="absolute inset-x-3 bottom-4 flex justify-center sm:bottom-6">
          {pensando ? (
            <span className="rounded-full bg-black/55 px-4 py-2 text-[13px] text-ink-2 backdrop-blur-md">{nombre.split(" ")[0]} está pensando…</span>
          ) : ultimoPaciente ? (
            <p
              key={turnos.lastIndexOf(ultimoPaciente)}
              className="enter max-w-2xl rounded-2xl bg-black/55 px-4 py-2.5 text-center text-[15px] leading-snug text-ink backdrop-blur-md sm:text-[17px]"
            >
              {ultimoPaciente.text}
            </p>
          ) : (
            <span className="rounded-full bg-black/55 px-4 py-2 text-[13px] text-ink-2 backdrop-blur-md">Conectado · saludá para empezar</span>
          )}
        </div>
      </div>

      {/* controles */}
      <div className="mx-auto w-full max-w-3xl">
        <Composer
          onSend={onSend}
          disabled={!listo || pensando}
          placeholder="Hablale al paciente…"
          before={
            <>
              <button
                type="button"
                disabled
                title="Voz: próximamente"
                aria-label="Micrófono (próximamente)"
                className="glass grid size-12 shrink-0 place-items-center rounded-full text-ink-3"
              >
                <Mic />
              </button>
              <button
                type="button"
                aria-label="Terminar consulta"
                onClick={onEnd}
                className="press order-last grid size-12 shrink-0 place-items-center rounded-full bg-danger text-white hover:brightness-110"
              >
                <PhoneDown />
              </button>
            </>
          }
        />
      </div>
    </div>
  );
}
