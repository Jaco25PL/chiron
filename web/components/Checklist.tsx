"use client";

import { Fragment } from "react";
import { Drawer } from "vaul";
import type { ItemChecklist } from "@/lib/api";
import { Check, Close } from "./icons";

// Beginner level: the grilla items the student must not forget, ticked by the backend as they are
// covered. Only what the app can see (questions, exam, studies); conduct is graded at the end.

const GRUPOS = [
  { tipo: "hecho", titulo: "Preguntá" },
  { tipo: "examen", titulo: "Examiná" },
  { tipo: "estudio", titulo: "Pedí" },
] as const;

const NOTA = "Saludar, presentarte, explicar y pedir permiso también cuentan: los evalúa el docente al final.";

function cuenta(items: ItemChecklist[]) {
  return { hechos: items.filter((i) => i.hecho).length, total: items.length };
}

/** "Checklist 12/44": opens the bottom sheet on mobile and shows/hides the side panel on desktop. */
export function ChecklistBoton({
  items,
  onClick,
  abierto,
  className = "",
}: {
  items: ItemChecklist[];
  onClick: () => void;
  abierto: boolean;
  className?: string;
}) {
  const { hechos, total } = cuenta(items);
  return (
    <button
      type="button"
      onClick={onClick}
      aria-expanded={abierto}
      aria-label={`Checklist: ${hechos} de ${total} hechos`}
      className={`press glass flex h-9 items-center gap-1.5 rounded-full px-3 text-[13px] font-medium text-ink-2 hover:text-ink ${className}`}
    >
      <Check width={15} height={15} className="text-accent" />
      Checklist
      <span className="font-mono tabular-nums text-ink-3">
        <span className="text-ink">{hechos}</span>/{total}
      </span>
    </button>
  );
}

/** Desktop: side panel next to the conversation. */
export function ChecklistPanel({ items, onCerrar }: { items: ItemChecklist[]; onCerrar: () => void }) {
  return (
    <aside
      aria-label="Checklist"
      className="glass enter mb-[max(12px,env(safe-area-inset-bottom))] hidden w-80 shrink-0 flex-col overflow-hidden rounded-[28px] lg:flex xl:w-96"
    >
      <div className="flex items-start justify-between gap-3 px-5 pb-3 pt-4">
        <Encabezado items={items} />
        <button
          type="button"
          aria-label="Ocultar checklist"
          onClick={onCerrar}
          className="press -mr-1 grid size-7 shrink-0 place-items-center rounded-full text-ink-3 hover:text-ink"
        >
          <Close width={16} height={16} />
        </button>
      </div>
      <Progreso items={items} />
      <div className="min-h-0 flex-1 overflow-y-auto px-5 pb-5 pt-4">
        <Lista items={items} />
      </div>
    </aside>
  );
}

/** Mobile: bottom sheet (vaul, drag to dismiss), opened from the pill. */
export function ChecklistSheet({
  items,
  abierto,
  onAbierto,
}: {
  items: ItemChecklist[];
  abierto: boolean;
  onAbierto: (a: boolean) => void;
}) {
  return (
    <Drawer.Root open={abierto} onOpenChange={onAbierto}>
      <Drawer.Portal>
        <Drawer.Overlay className="fixed inset-0 z-40 bg-black/60" />
        <Drawer.Content className="fixed inset-x-0 bottom-0 z-50 mx-auto flex max-h-[85dvh] w-full max-w-xl flex-col rounded-t-[28px] border border-b-0 border-line-strong bg-bg-2 outline-none">
          <div className="mx-auto mt-3 h-1.5 w-10 shrink-0 rounded-full bg-line-strong" />
          <div className="px-6 pb-3 pt-4">
            <Encabezado items={items} titulo={Drawer.Title} descripcion={Drawer.Description} />
          </div>
          <Progreso items={items} />
          <div className="min-h-0 overflow-y-auto px-6 pb-[max(24px,env(safe-area-inset-bottom))] pt-4">
            <Lista items={items} />
          </div>
        </Drawer.Content>
      </Drawer.Portal>
    </Drawer.Root>
  );
}

function Encabezado({
  items,
  titulo: Titulo = "p",
  descripcion: Descripcion = "p",
}: {
  items: ItemChecklist[];
  titulo?: React.ElementType;
  descripcion?: React.ElementType;
}) {
  const { hechos, total } = cuenta(items);
  return (
    <div className="min-w-0">
      <Titulo className="flex items-baseline gap-2 text-[15px] font-semibold tracking-tight">
        Que no se te pase
        <span className="font-mono text-[13px] font-normal tabular-nums text-ink-3">
          <span className="text-accent">{hechos}</span>/{total}
        </span>
      </Titulo>
      <Descripcion className="mt-0.5 text-[12.5px] text-ink-3">Se tachan solos a medida que los hacés.</Descripcion>
    </div>
  );
}

/** Thin progress bar: scaleX, so only transform animates. */
function Progreso({ items }: { items: ItemChecklist[] }) {
  const { hechos, total } = cuenta(items);
  return (
    <div className="mx-5 h-[3px] shrink-0 overflow-hidden rounded-full bg-line">
      <div
        className="h-full origin-left rounded-full bg-accent transition-transform duration-[250ms] ease-[var(--ease-out)] motion-reduce:transition-none"
        style={{ transform: `scaleX(${total ? hechos / total : 0})` }}
      />
    </div>
  );
}

function Lista({ items }: { items: ItemChecklist[] }) {
  return (
    <div className="flex flex-col gap-5">
      {GRUPOS.map(({ tipo, titulo }) => {
        const grupo = items.filter((i) => i.tipo === tipo);
        if (!grupo.length) return null;
        return (
          <section key={tipo} aria-label={titulo}>
            <h3 className="mb-1 flex items-baseline justify-between text-[11px] font-medium uppercase tracking-[0.14em] text-ink-3">
              {titulo}
              <span className="font-mono normal-case tracking-normal tabular-nums">
                {cuenta(grupo).hechos}/{grupo.length}
              </span>
            </h3>
            <ul>
              {grupo.map((i, n) => (
                <Fragment key={i.id}>
                  {/* the grilla's own sections, in its order, like the paper grilla students know */}
                  {i.seccion && i.seccion !== grupo[n - 1]?.seccion && (
                    <li aria-hidden className="pb-0.5 pt-2.5 text-[12px] text-ink-3 first:pt-0.5">
                      {i.seccion}
                    </li>
                  )}
                  <Item item={i} />
                </Fragment>
              ))}
            </ul>
          </section>
        );
      })}
      <p className="text-pretty text-[12px] leading-snug text-ink-3">{NOTA}</p>
    </div>
  );
}

/** Done: the check pops in and the text dims, crossed out. Only transform/opacity animate (the
 *  strike-through appears at once), and only when the backend ticks it, never on load. */
function Item({ item }: { item: ItemChecklist }) {
  const anim = "duration-200 ease-[var(--ease-out)] motion-reduce:transition-none";
  return (
    <li data-hecho={item.hecho} className="flex items-start gap-2.5 py-1.5 text-[13.5px] leading-snug">
      <span className="relative mt-px grid size-[18px] shrink-0 place-items-center rounded-full border border-line-strong">
        <span
          className={`absolute -inset-px grid place-items-center rounded-full bg-accent text-accent-ink transition-[transform,opacity] ${anim} ${
            item.hecho ? "scale-100 opacity-100" : "scale-50 opacity-0"
          }`}
        >
          <Check width={12} height={12} strokeWidth={2.5} />
        </span>
      </span>
      <span
        className={`transition-opacity ${anim} ${item.hecho ? "text-ink-2 line-through decoration-ink-3 opacity-60" : "text-ink"}`}
      >
        {item.hecho && <span className="sr-only">Hecho: </span>}
        {item.texto}
      </span>
    </li>
  );
}
