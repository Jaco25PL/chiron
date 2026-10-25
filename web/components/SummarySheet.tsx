"use client";

import Link from "next/link";
import { useState } from "react";
import { Drawer } from "vaul";
import type { Calificacion, Feedback, Resumen } from "@/lib/api";
import { Check, ChevronLeft } from "./icons";

/** Bottom sheet with the docente's correction (vaul: drag to dismiss, desktop too). It opens as soon as the
 *  consultation ends, with a calm waiting state while the docente grades it (one LLM call, several seconds). */
export function SummarySheet({
  resumen,
  corrigiendo,
  onClose,
}: {
  resumen: Resumen | null;
  corrigiendo: boolean;
  onClose: () => void;
}) {
  return (
    <Drawer.Root open={!!resumen || corrigiendo} dismissible={!corrigiendo} onOpenChange={(o) => !o && onClose()}>
      <Drawer.Portal>
        <Drawer.Overlay className="fixed inset-0 z-40 bg-black/60" />
        <Drawer.Content className="fixed inset-x-0 bottom-0 z-50 mx-auto flex max-h-[88dvh] w-full max-w-xl flex-col rounded-t-[28px] border border-b-0 border-line-strong bg-bg-2 outline-none">
          <div className="mx-auto mt-3 h-1.5 w-10 shrink-0 rounded-full bg-line-strong" />
          <div className="flex flex-col gap-6 overflow-y-auto px-6 pb-[max(24px,env(safe-area-inset-bottom))] pt-5">
            <div>
              <Drawer.Title className="text-xl font-semibold tracking-tight">Consulta terminada</Drawer.Title>
              <Drawer.Description className="mt-1 text-sm text-ink-2">
                {!resumen
                  ? "El docente está corrigiendo tu consulta…"
                  : !resumen.feedback
                    ? "Esto es lo que obtuviste en la consulta."
                    : resumen.feedback.parcial
                      ? "El docente no pudo corregirla a fondo ahora: esto es lo que la app registró contra la grilla."
                      : "La corrección del docente, contra la grilla de la estación."}
              </Drawer.Description>
            </div>

            {!resumen ? <Corrigiendo /> : <Correccion resumen={resumen} />}
          </div>
        </Drawer.Content>
      </Drawer.Portal>
    </Drawer.Root>
  );
}

function Corrigiendo() {
  return (
    <div role="status" className="enter flex flex-col items-center gap-4 py-10 text-center">
      <span className="size-9 animate-spin rounded-full border-2 border-line-strong border-t-accent" aria-hidden />
      <p className="max-w-xs text-sm text-ink-3">Revisa la grilla ítem por ítem. Tarda unos segundos.</p>
    </div>
  );
}

function Correccion({ resumen }: { resumen: Resumen }) {
  const fb = resumen.feedback;
  return (
    <>
      <div className="enter flex items-center gap-5">
        <Anillo
          pct={fb ? fb.score : Math.round((resumen.revealed_facts.length / Math.max(resumen.total_facts, 1)) * 100)}
        />
        <div>
          {fb && (
            <p
              className="text-4xl font-semibold tabular-nums tracking-tight"
              aria-label={`Puntaje: ${fb.score} de 100`}
            >
              {fb.score}
              <span className="text-xl text-ink-3">/100</span>
            </p>
          )}
          <p className="text-sm text-ink-2">
            <span className="tabular-nums">
              {resumen.revealed_facts.length}/{resumen.total_facts}
            </span>{" "}
            datos de la historia que obtuviste
          </p>
        </div>
      </div>

      {fb && (
        <>
          <Lista titulo="Lo que hiciste bien" items={fb.bien} marca="bien" />
          <Lista titulo="Te faltó" items={fb.falto} marca="falto" />
          <Lista titulo="Para la próxima" items={fb.consejos} marca="consejo" />
        </>
      )}

      <Bloque titulo="Examen físico" items={resumen.exams_done_labels} vacio="No realizaste maniobras." />
      <Bloque titulo="Paraclínica" items={resumen.studies_requested} vacio="No pediste estudios." />
      <div>
        <h3 className="mb-2 text-[11px] font-medium uppercase tracking-[0.14em] text-ink-3">Tu planteo diagnóstico</h3>
        <p className="text-[15px] text-ink">
          {resumen.diagnosis_proposed ?? <span className="text-ink-3">No planteaste un diagnóstico.</span>}
        </p>
      </div>

      {fb && <Grilla items={fb.items} />}

      <Link
        href="/"
        className="press flex h-12 shrink-0 items-center justify-center rounded-full bg-ink text-[15px] font-medium text-bg hover:bg-white"
      >
        Nueva consulta
      </Link>
    </>
  );
}

function Lista({ titulo, items, marca }: { titulo: string; items: string[]; marca: "bien" | "falto" | "consejo" }) {
  if (!items.length) return null;
  return (
    <section>
      <h3 className="mb-2.5 text-[11px] font-medium uppercase tracking-[0.14em] text-ink-3">{titulo}</h3>
      <ul className="flex flex-col gap-2">
        {items.map((t) => (
          <li key={t} className="flex gap-2.5 text-[15px] leading-snug text-ink">
            {marca === "bien" ? (
              <Check width={16} height={16} className="mt-0.5 shrink-0 text-accent" />
            ) : (
              <span
                aria-hidden
                className={`mx-[5px] mt-[8px] size-1.5 shrink-0 rounded-full ${marca === "consejo" ? "bg-accent" : "bg-ink-3"}`}
              />
            )}
            <span>{t}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

const ESTILO: Record<Calificacion, string> = {
  Excelente: "bg-accent/15 text-accent",
  Bien: "bg-glass-strong text-ink",
  Regular: "bg-glass text-ink-2",
  "No realizado": "text-ink-3",
};

/** Every grilla item with its rating; collapsed by default (the summary above is what matters). */
function Grilla({ items }: { items: Feedback["items"] }) {
  const [abierta, setAbierta] = useState(false);
  return (
    <section className="rounded-2xl border border-line">
      <button
        onClick={() => setAbierta((a) => !a)}
        aria-expanded={abierta}
        className="press flex w-full items-center justify-between px-4 py-3 text-left text-sm font-medium text-ink-2 hover:text-ink"
      >
        Grilla completa
        <span className="flex items-center gap-2 text-xs text-ink-3">
          {items.length} ítems
          <ChevronLeft
            width={16}
            height={16}
            className="transition-transform duration-200 [transition-timing-function:var(--ease-out)]"
            style={{ transform: abierta ? "rotate(90deg)" : "rotate(-90deg)" }}
          />
        </span>
      </button>
      {abierta && (
        <ul className="enter flex flex-col border-t border-line px-4 py-2">
          {items.map((it) => (
            <li key={it.id} className="flex items-start justify-between gap-3 py-2 text-[14px]">
              <span className={it.tipo === "global" ? "text-ink-2 italic" : "text-ink-2"}>{it.texto}</span>
              <span
                className={`shrink-0 rounded-full px-2 py-0.5 text-[12px] font-medium ${
                  it.calificacion ? ESTILO[it.calificacion] : "text-ink-3"
                }`}
              >
                {it.calificacion ?? "Sin corregir"}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function Bloque({ titulo, items, vacio }: { titulo: string; items: string[]; vacio: string }) {
  return (
    <div>
      <h3 className="mb-2 text-[11px] font-medium uppercase tracking-[0.14em] text-ink-3">{titulo}</h3>
      {items.length ? (
        <div className="flex flex-wrap gap-1.5">
          {items.map((i) => (
            <span key={i} className="rounded-full border border-line px-2.5 py-1 font-mono text-[12px] text-ink-2">
              {i}
            </span>
          ))}
        </div>
      ) : (
        <p className="text-sm text-ink-3">{vacio}</p>
      )}
    </div>
  );
}

function Anillo({ pct }: { pct: number }) {
  const r = 30;
  const c = 2 * Math.PI * r;
  return (
    <svg width="76" height="76" viewBox="0 0 76 76" className="shrink-0 -rotate-90" aria-hidden>
      <circle cx="38" cy="38" r={r} fill="none" stroke="var(--line-strong)" strokeWidth="6" />
      <circle
        cx="38"
        cy="38"
        r={r}
        fill="none"
        stroke="var(--accent)"
        strokeWidth="6"
        strokeLinecap="round"
        strokeDasharray={`${(pct / 100) * c} ${c}`}
      />
    </svg>
  );
}
