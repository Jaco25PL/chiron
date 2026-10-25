"use client";

import { useEffect, useRef } from "react";
import type { Caso, Turno } from "@/lib/api";
import { Composer } from "./Composer";
import { Stethoscope } from "./icons";

export function ChatView({
  caso,
  turnos,
  pensando,
  listo,
  onSend,
}: {
  caso: Caso | null;
  turnos: Turno[];
  pensando: boolean;
  listo: boolean;
  onSend: (t: string) => void;
}) {
  const fin = useRef<HTMLDivElement>(null);
  useEffect(() => {
    fin.current?.scrollIntoView({ block: "end" });
  }, [turnos.length, pensando]);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto flex w-full max-w-2xl flex-col gap-3 px-4 py-6">
          {turnos.length === 0 && <Vacio caso={caso} />}
          {turnos.map((t, i) => (
            <Mensaje key={i} turno={t} />
          ))}
          {pensando && <Escribiendo />}
          <div ref={fin} />
        </div>
      </div>
      <div className="mx-auto w-full max-w-2xl px-4 pb-[max(16px,env(safe-area-inset-bottom))] pt-2">
        <Composer onSend={onSend} disabled={!listo || pensando} />
      </div>
    </div>
  );
}

function Mensaje({ turno }: { turno: Turno }) {
  if (turno.role === "docente") {
    return (
      <div className="enter my-1 rounded-2xl border border-accent/20 bg-accent/[0.06] p-4">
        <div className="mb-2 flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-[0.14em] text-accent">
          <Stethoscope width={14} height={14} /> Docente
        </div>
        <p className="whitespace-pre-wrap font-mono text-[13px] leading-relaxed text-ink">{turno.text}</p>
      </div>
    );
  }
  const propio = turno.role === "estudiante";
  return (
    <div className={`flex ${propio ? "justify-end" : "justify-start"}`}>
      <p
        className={`max-w-[82%] whitespace-pre-wrap rounded-[22px] px-4 py-2.5 text-[15.5px] leading-snug ${
          propio ? "rounded-br-md bg-ink text-bg" : "glass enter rounded-bl-md text-ink"
        }`}
      >
        {turno.text}
      </p>
    </div>
  );
}

function Escribiendo() {
  return (
    <div className="glass enter flex w-fit items-center gap-1 rounded-[22px] rounded-bl-md px-4 py-3.5" aria-label="El paciente está respondiendo">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="size-1.5 animate-pulse rounded-full bg-ink-2"
          style={{ animationDelay: `${i * 160}ms` }}
        />
      ))}
    </div>
  );
}

function Vacio({ caso }: { caso: Caso | null }) {
  return (
    <div className="flex flex-col items-center gap-2 py-16 text-center">
      <p className="text-sm text-ink-3">La consulta empieza cuando mandes el primer mensaje.</p>
      <p className="max-w-sm text-pretty text-[15px] text-ink-2">
        {caso ? `${caso.paciente.nombre.split(" ")[0]} está esperando. ` : ""}Saludá, presentate y preguntá como en la estación.
      </p>
    </div>
  );
}
