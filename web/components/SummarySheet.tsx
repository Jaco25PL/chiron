"use client";

import Link from "next/link";
import { Drawer } from "vaul";
import type { Resumen } from "@/lib/api";

/** Bottom sheet with the consultation summary (vaul: drag to dismiss, desktop too). */
export function SummarySheet({ resumen, onClose }: { resumen: Resumen | null; onClose: () => void }) {
  const pct = resumen ? Math.round((resumen.revealed_facts.length / Math.max(resumen.total_facts, 1)) * 100) : 0;
  return (
    <Drawer.Root open={!!resumen} onOpenChange={(o) => !o && onClose()}>
      <Drawer.Portal>
        <Drawer.Overlay className="fixed inset-0 z-40 bg-black/60" />
        <Drawer.Content className="fixed inset-x-0 bottom-0 z-50 mx-auto flex max-h-[88dvh] w-full max-w-xl flex-col rounded-t-[28px] border border-b-0 border-line-strong bg-bg-2 outline-none">
          <div className="mx-auto mt-3 h-1.5 w-10 shrink-0 rounded-full bg-line-strong" />
          {resumen && (
            <div className="flex flex-col gap-6 overflow-y-auto px-6 pb-[max(24px,env(safe-area-inset-bottom))] pt-5">
              <div>
                <Drawer.Title className="text-xl font-semibold tracking-tight">Consulta terminada</Drawer.Title>
                <Drawer.Description className="mt-1 text-sm text-ink-2">
                  El feedback completo contra la grilla llega en el próximo paso. Por ahora, esto es lo que obtuviste.
                </Drawer.Description>
              </div>

              <div className="flex items-center gap-5">
                <Anillo pct={pct} />
                <div>
                  <p className="text-3xl font-semibold tabular-nums tracking-tight">
                    {resumen.revealed_facts.length}
                    <span className="text-ink-3">/{resumen.total_facts}</span>
                  </p>
                  <p className="text-sm text-ink-2">datos de la historia que obtuviste</p>
                </div>
              </div>

              <Bloque titulo="Examen físico" items={resumen.exams_done_labels} vacio="No realizaste maniobras." />
              <Bloque titulo="Paraclínica" items={resumen.studies_requested} vacio="No pediste estudios." />
              <div>
                <h3 className="mb-2 text-[11px] font-medium uppercase tracking-[0.14em] text-ink-3">Planteo diagnóstico</h3>
                <p className="text-[15px] text-ink">{resumen.diagnosis_proposed ?? <span className="text-ink-3">No planteaste un diagnóstico.</span>}</p>
              </div>

              <Link
                href="/"
                className="press flex h-12 items-center justify-center rounded-full bg-ink text-[15px] font-medium text-bg hover:bg-white"
              >
                Nueva consulta
              </Link>
            </div>
          )}
        </Drawer.Content>
      </Drawer.Portal>
    </Drawer.Root>
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
    <svg width="76" height="76" viewBox="0 0 76 76" className="shrink-0 -rotate-90" aria-label={`${pct}%`}>
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
