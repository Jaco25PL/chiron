"use client";

import Link from "next/link";
import { useState } from "react";
import { formatoTiempo, useConsulta, useCuentaRegresiva } from "@/lib/useConsulta";
import { ChatView } from "./ChatView";
import { FaceView } from "./FaceView";
import { Chat, ChevronLeft, Clock, Video } from "./icons";
import { Segmented } from "./Segmented";
import { SummarySheet } from "./SummarySheet";

type Modo = "chat" | "cara";

/** Consultation screen. Chat and face-to-face share the same session, so the mode can switch at any time. */
export function Consulta({ caseId, modoInicial }: { caseId: string; modoInicial: Modo }) {
  const [modo, setModo] = useState<Modo>(modoInicial);
  const c = useConsulta(caseId);
  const restante = useCuentaRegresiva(c.inicio);
  const nombre = c.caso?.paciente.nombre.split(" ").slice(0, 2).join(" ");

  return (
    <div className="flex h-dvh flex-col">
      <header className="grid grid-cols-[1fr_auto_1fr] items-center gap-2 px-3 pb-3 pt-[max(12px,env(safe-area-inset-top))] sm:px-6">
        <div className="flex min-w-0 items-center gap-2">
          <Link href="/" aria-label="Volver" className="press glass grid size-9 shrink-0 place-items-center rounded-full text-ink-2 hover:text-ink">
            <ChevronLeft width={18} height={18} />
          </Link>
          <div className="hidden min-w-0 sm:block">
            <p className="truncate text-sm font-medium">{nombre ?? " "}</p>
            <p className="truncate text-xs text-ink-3">{c.caso?.titulo ?? " "}</p>
          </div>
        </div>

        <Segmented
          id="modo"
          size="sm"
          value={modo}
          onChange={setModo}
          options={[
            { value: "chat", label: <><Chat width={15} height={15} /> Chat</> },
            { value: "cara", label: <><Video width={15} height={15} /> Cara a cara</> },
          ]}
        />

        <div className="flex items-center justify-end gap-2">
          <span
            className={`glass flex h-9 items-center gap-1.5 rounded-full px-3 font-mono text-[13px] tabular-nums transition-colors ${
              restante < 0 ? "text-danger" : restante <= 60 ? "text-[#ffd60a]" : "text-ink-2"
            }`}
            title="Tiempo de la estación"
          >
            <Clock width={15} height={15} />
            {formatoTiempo(restante)}
          </span>
          {modo === "chat" && (
            <button
              onClick={c.terminar}
              disabled={!c.listo}
              className="press hidden h-9 rounded-full bg-danger/15 px-3.5 text-[13px] font-medium text-danger hover:bg-danger/25 disabled:opacity-40 sm:block"
            >
              Terminar
            </button>
          )}
        </div>
      </header>

      {modo === "chat" ? (
        <ChatView caso={c.caso} turnos={c.turnos} pensando={c.pensando} listo={c.listo} onSend={c.enviar} />
      ) : (
        <FaceView
          caso={c.caso}
          turnos={c.turnos}
          pensando={c.pensando}
          listo={c.listo}
          onSend={c.enviar}
          onEnd={c.terminar}
        />
      )}

      {modo === "chat" && (
        <button
          onClick={c.terminar}
          disabled={!c.listo}
          className="press fixed bottom-[calc(max(16px,env(safe-area-inset-bottom))+118px)] right-4 h-9 rounded-full bg-danger/15 px-3.5 text-[13px] font-medium text-danger backdrop-blur disabled:opacity-40 sm:hidden"
        >
          Terminar
        </button>
      )}

      <SummarySheet resumen={c.resumen} onClose={() => c.setResumen(null)} />
    </div>
  );
}
