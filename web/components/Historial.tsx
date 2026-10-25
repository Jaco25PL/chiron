"use client";

import { useEffect, useState } from "react";
import { Clock } from "@/components/icons";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { api, type ConsultaPasada } from "@/lib/api";

const ULTIMAS = 5; // the average and its comparison use the last five consultations
const BARRAS = 12; // columns in the chart

const fecha = (iso: string) => {
  const d = new Date(iso);
  const dias = Math.floor((Date.now() - d.getTime()) / 86_400_000);
  if (dias < 1 && new Date().getDate() === d.getDate()) return "Hoy";
  if (dias < 2) return "Ayer";
  return d.toLocaleDateString("es-UY", { day: "numeric", month: "short" });
};

const promedio = (xs: ConsultaPasada[]) => Math.round(xs.reduce((a, x) => a + x.score, 0) / xs.length);

/** Side menu with the student's scores: average, how it's going, what to remember next time, and every
 *  finished consultation. Loaded each time it opens, so it's current after every consultation. */
export function Historial() {
  const [abierto, setAbierto] = useState(false);
  const [items, setItems] = useState<ConsultaPasada[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!abierto) return;
    api
      .historial()
      .then((xs) => {
        setItems(xs);
        setError("");
      })
      .catch((e: Error) => setError(e.message));
  }, [abierto]);

  return (
    <Sheet open={abierto} onOpenChange={setAbierto}>
      <SheetTrigger
        aria-label="Historial"
        className="press flex h-9 items-center gap-1.5 rounded-full border border-line-strong bg-glass px-3 text-[13px] text-ink-2 hover:text-ink"
      >
        <Clock width={16} height={16} />
        <span className="hidden sm:inline">Historial</span>
      </SheetTrigger>
      <SheetContent className="w-full gap-0 overflow-y-auto sm:max-w-md">
        <SheetHeader className="px-5 pb-2 pt-5">
          <SheetTitle className="text-lg font-semibold tracking-tight">Tu historial</SheetTitle>
          <SheetDescription className="text-[13px] text-ink-3">
            Tu puntaje en cada consulta terminada, según la grilla.
          </SheetDescription>
        </SheetHeader>
        <div className="flex flex-col gap-6 px-5 pb-8 pt-3">
          {error ? (
            <p className="text-[14px] text-ink-2">{error}</p>
          ) : !items ? (
            <p className="text-[14px] text-ink-3">Cargando…</p>
          ) : !items.length ? (
            <p className="text-pretty text-[14px] leading-relaxed text-ink-2">
              Todavía no terminaste ninguna consulta. Cuando termines una, acá vas a ver tu puntaje y qué repasar para
              la próxima.
            </p>
          ) : (
            <Contenido items={items} />
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}

function Contenido({ items }: { items: ConsultaPasada[] }) {
  const ultimas = items.slice(0, ULTIMAS);
  const anteriores = items.slice(ULTIMAS, ULTIMAS * 2);
  const actual = promedio(ultimas);
  const cambio = anteriores.length ? actual - promedio(anteriores) : null;
  const notas = items[0].para_la_proxima;

  return (
    <>
      <section className="flex items-end justify-between gap-4">
        <div>
          <p className="text-[13px] text-ink-3">Promedio de las últimas {ultimas.length}</p>
          <p className="text-5xl font-semibold tracking-tight tabular-nums">
            {actual}
            <span className="text-xl text-ink-3">/100</span>
          </p>
        </div>
        {cambio !== null && (
          <p className="pb-1.5 text-right text-[13px] text-ink-2">
            <span className={cambio >= 0 ? "text-live" : "text-danger"} aria-hidden>
              {cambio >= 0 ? "▲" : "▼"}
            </span>{" "}
            {cambio === 0 ? "Igual" : `${cambio > 0 ? "+" : "−"}${Math.abs(cambio)}`} vs. las {anteriores.length}{" "}
            anteriores
          </p>
        )}
      </section>

      <Evolucion items={items.slice(0, BARRAS).reverse()} />

      {notas.length > 0 && (
        <section className="rounded-2xl border border-line p-4">
          <h3 className="mb-2 text-[12px] font-medium uppercase tracking-[0.14em] text-accent">Para la próxima</h3>
          <ul className="flex flex-col gap-1.5 text-[14px] leading-snug text-ink-2">
            {notas.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <h3 className="mb-1 text-[13px] text-ink-3">Consultas</h3>
        <ul className="flex flex-col divide-y divide-line">
          {items.map((c) => (
            <li key={c.id} className="flex flex-col gap-1.5 py-3">
              <div className="flex items-baseline justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-[15px] font-medium">
                    {c.paciente.nombre.split(" ").slice(0, 2).join(" ")}
                  </p>
                  <p className="text-[12px] text-ink-3">
                    {fecha(c.fecha)} · {c.modo === "cara" ? "Cara a cara" : "Chat"} ·{" "}
                    {c.nivel === "principiante" ? "Principiante" : "Normal"}
                  </p>
                </div>
                <p className="shrink-0 text-xl font-semibold tabular-nums">
                  {c.score}
                  <span className="text-[13px] font-normal text-ink-3">/100</span>
                </p>
              </div>
              {c.para_la_proxima[0] && <p className="text-[13px] leading-snug text-ink-2">{c.para_la_proxima[0]}</p>}
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}

/** Score per consultation, oldest to newest: one column each, hover or focus one to read it. The list
 *  below is the table view. */
function Evolucion({ items }: { items: ConsultaPasada[] }) {
  const [activa, setActiva] = useState(items.length - 1);
  const c = items[activa] ?? items[items.length - 1];
  return (
    <section aria-label="Evolución del puntaje">
      <p className="mb-2 flex justify-between text-[13px]">
        <span className="text-ink-3">Evolución</span>
        <span className="text-ink-2" aria-live="polite">
          {c.paciente.nombre.split(" ")[0]} · {fecha(c.fecha)} ·{" "}
          <span className="tabular-nums text-ink">{c.score}</span>
        </span>
      </p>
      <div
        className="relative flex h-24 items-end gap-1.5 border-b border-line"
        onMouseLeave={() => setActiva(items.length - 1)}
      >
        <div className="pointer-events-none absolute inset-x-0 top-1/2 border-t border-line" aria-hidden>
          <span className="absolute right-0 -translate-y-full pb-0.5 text-[10px] tabular-nums text-ink-3">50</span>
        </div>
        {items.map((x, i) => (
          <button
            key={x.id}
            type="button"
            aria-label={`${x.paciente.nombre}, ${fecha(x.fecha)}: ${x.score} de 100`}
            onMouseEnter={() => setActiva(i)}
            onFocus={() => setActiva(i)}
            onClick={() => setActiva(i)}
            className="group flex h-full max-w-6 flex-1 items-end outline-none"
          >
            <span
              className={`block w-full origin-bottom rounded-t-[4px] bg-accent transition-opacity duration-150 motion-safe:animate-[crecer_300ms_var(--ease-out)_both] ${
                i === activa ? "opacity-100" : "opacity-45 group-hover:opacity-80"
              } group-focus-visible:ring-2 group-focus-visible:ring-ink`}
              style={{ height: `${Math.max(x.score, 2)}%`, animationDelay: `${i * 20}ms` }}
            />
          </button>
        ))}
      </div>
    </section>
  );
}
