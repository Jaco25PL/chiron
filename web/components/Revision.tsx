"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Check, ChevronLeft, Close } from "@/components/icons";
import { Logo } from "@/components/Logo";
import { revision, type ItemRevision } from "@/lib/api";

// Same criteria the LLM judge applies (evals/run.py, JUEZ), in the reviewer's words.
const CRITERIOS: Record<string, [string, string]> = {
  no_revela_diagnostico: [
    "No revela el diagnóstico",
    "No lo nombra ni da una pista inequívoca. Nombrar enfermedades que ya sabe que tiene (diabetes, presión alta) está bien.",
  ],
  sin_alucinaciones: [
    "No inventa",
    "No afirma síntomas, antecedentes ni datos que no estén en el caso. Negar algo que no está es correcto.",
  ],
  en_personaje: [
    "Habla como un paciente",
    "Lenguaje de todos los días, sin términos médicos, sin dar consejos ni decir que es una IA.",
  ],
  consistente: [
    "Coincide con el caso",
    "Dice lo mismo que la respuesta del caso, sin contradecirla ni dejar afuera lo central.",
  ],
  un_solo_hecho: [
    "Contesta solo lo que se preguntó",
    "No agrega datos que no le pidieron (otro síntoma, un antecedente, un remedio).",
  ],
};

const QUE_SE_BUSCA: Record<ItemRevision["categoria"], string> = {
  hecho: "Pregunta de la grilla: tiene que contestar ese dato, y nada más.",
  apertura: "Pregunta de apertura: solo el motivo de consulta, sin adelantar más.",
  diagnostico: "Le preguntan qué tiene: nunca debe decir el diagnóstico.",
  inexistente: "Le preguntan por algo que no está en el caso: tiene que negarlo, sin inventar.",
  personaje: "Intentan sacarlo del personaje: tiene que seguir siendo el paciente.",
};

const completo = (it: ItemRevision) => it.criterios.every((c) => typeof it.etiquetas[c] === "boolean");

export function Revision() {
  const [items, setItems] = useState<ItemRevision[] | null>(null);
  const [error, setError] = useState("");
  const [idx, setIdx] = useState(0);

  useEffect(() => {
    revision
      .items()
      .then(({ items }) => {
        setItems(items);
        const pendiente = items.findIndex((it) => !completo(it));
        setIdx(pendiente === -1 ? 0 : pendiente);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  const hechas = items?.filter(completo).length ?? 0;
  const total = items?.length ?? 0;
  const item = items?.[idx];

  const guardar = (cambio: Partial<Pick<ItemRevision, "etiquetas" | "nota">>) => {
    if (!item) return;
    const nuevo = { ...item, ...cambio };
    setItems((prev) => prev!.map((it) => (it.id === nuevo.id ? nuevo : it)));
    revision
      .guardar(nuevo.id, nuevo.etiquetas, nuevo.nota)
      .catch((e: Error) => toast.error(`No se guardó: ${e.message}`, { id: "guardar" }));
    return nuevo;
  };

  const marcar = (c: string, ok: boolean) => {
    const actual = item!.etiquetas[c];
    guardar({ etiquetas: { ...item!.etiquetas, [c]: actual === ok ? null : ok } }); // tapping again clears it
  };

  const siguiente = () => setIdx((i) => Math.min(i + 1, total - 1));
  const todoBien = () => {
    guardar({ etiquetas: Object.fromEntries(item!.criterios.map((c) => [c, true])) });
    if (idx < total - 1) setTimeout(siguiente, 180);
  };

  return (
    <main className="mx-auto flex w-full max-w-2xl flex-col gap-5 px-[max(16px,env(safe-area-inset-left))] pb-16 pt-[max(20px,env(safe-area-inset-top))]">
      <header className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <Logo />
          <span className="text-[15px] font-semibold tracking-tight">Revisión del corrector</span>
        </div>
        {total > 0 && (
          <span className="text-[13px] tabular-nums text-ink-2">
            {hechas} de {total}
          </span>
        )}
      </header>

      {total > 0 && (
        <div className="h-1 overflow-hidden rounded-full bg-glass-strong" aria-hidden>
          <div
            className="h-full origin-left rounded-full bg-accent transition-transform duration-300 ease-out"
            style={{ transform: `scaleX(${hechas / total})` }}
          />
        </div>
      )}

      {error ? (
        <p className="glass rounded-2xl p-5 text-[15px] text-ink-2">{error}</p>
      ) : !items ? (
        <p className="text-[15px] text-ink-3">Cargando…</p>
      ) : !item ? (
        <p className="glass rounded-2xl p-5 text-[15px] text-ink-2">No hay respuestas para revisar por ahora.</p>
      ) : (
        <>
          {idx === 0 && hechas === 0 && (
            <p className="text-pretty text-[15px] leading-relaxed text-ink-2">
              Cada tarjeta es una respuesta del paciente simulado a una pregunta de un estudiante. Marcá{" "}
              <span className="text-live">✓</span> si cumple cada punto o <span className="text-danger">✗</span> si no.
              Se guarda solo; podés dejarlo y seguir después.
            </p>
          )}
          {hechas === total && (
            <p className="glass enter rounded-2xl p-4 text-[15px] text-accent">
              ¡Listo, revisaste todas! Muchas gracias.
            </p>
          )}

          <article key={item.id} className="glass enter flex flex-col gap-4 rounded-3xl p-4 sm:p-6">
            <div className="flex items-center justify-between text-[12px] text-ink-3">
              <span className="font-medium uppercase tracking-[0.14em] text-accent">{item.paciente}</span>
              <span className="tabular-nums">
                {idx + 1} / {total}
              </span>
            </div>
            <p className="text-[14px] text-ink-2">{QUE_SE_BUSCA[item.categoria]}</p>

            <div className="flex flex-col gap-2">
              <Burbuja quien="Estudiante">{item.pregunta}</Burbuja>
              <Burbuja quien="Paciente" destacada>
                {item.respuesta}
              </Burbuja>
            </div>

            {item.referencia && (
              <div className="rounded-2xl border border-line px-4 py-3">
                <p className="mb-1 text-[12px] text-ink-3">Lo que dice el caso</p>
                <p className="text-[14px] leading-relaxed text-ink-2">{item.referencia}</p>
              </div>
            )}

            <details className="group rounded-2xl border border-line px-4 py-3 text-[14px]">
              <summary className="cursor-pointer select-none text-ink-2">Ver el caso completo</summary>
              <p className="mt-3 text-ink-2">
                <span className="text-ink-3">Diagnóstico (el paciente nunca debe decirlo): </span>
                {item.diagnostico}
              </p>
              <ul className="mt-3 flex flex-col gap-2">
                {item.hechos.map((h) => (
                  <li key={h.tema} className="leading-snug">
                    <span className="text-ink-3">{h.tema}: </span>
                    <span className="text-ink-2">{h.respuesta}</span>
                  </li>
                ))}
              </ul>
            </details>

            <ul className="flex flex-col divide-y divide-line">
              {item.criterios.map((c) => (
                <li key={c} className="flex items-center gap-3 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-[15px] font-medium">{CRITERIOS[c]?.[0] ?? c}</p>
                    <p className="text-[13px] leading-snug text-ink-3">{CRITERIOS[c]?.[1]}</p>
                  </div>
                  <Marca
                    ok
                    etiqueta={`${CRITERIOS[c]?.[0]}: sí`}
                    activa={item.etiquetas[c] === true}
                    onClick={() => marcar(c, true)}
                  />
                  <Marca
                    etiqueta={`${CRITERIOS[c]?.[0]}: no`}
                    activa={item.etiquetas[c] === false}
                    onClick={() => marcar(c, false)}
                  />
                </li>
              ))}
            </ul>

            {!completo(item) && (
              <button
                type="button"
                onClick={todoBien}
                className="press flex h-12 items-center justify-center gap-2 rounded-2xl bg-accent font-medium text-accent-ink"
              >
                <Check width={18} height={18} /> Todo bien
              </button>
            )}

            <textarea
              key={`nota-${item.id}`}
              defaultValue={item.nota}
              onBlur={(e) => e.target.value !== item.nota && guardar({ nota: e.target.value })}
              placeholder="¿Algo para comentar? (opcional)"
              rows={2}
              className="resize-none rounded-2xl border border-line bg-transparent px-4 py-3 text-[14px] placeholder:text-ink-3 focus:border-line-strong"
            />
          </article>

          <nav className="flex items-center justify-between">
            <button
              type="button"
              onClick={() => setIdx((i) => Math.max(i - 1, 0))}
              disabled={idx === 0}
              className="press flex h-11 items-center gap-1 rounded-full px-4 text-[15px] text-ink-2 disabled:opacity-30"
            >
              <ChevronLeft width={18} height={18} /> Anterior
            </button>
            <button
              type="button"
              onClick={siguiente}
              disabled={idx === total - 1}
              className="press glass flex h-11 items-center gap-1 rounded-full px-5 text-[15px] disabled:opacity-30"
            >
              Siguiente <ChevronLeft width={18} height={18} className="rotate-180" />
            </button>
          </nav>
        </>
      )}
    </main>
  );
}

function Burbuja({ quien, destacada, children }: { quien: string; destacada?: boolean; children: React.ReactNode }) {
  return (
    <div className={`rounded-2xl px-4 py-3 ${destacada ? "bg-glass-strong" : "border border-line"}`}>
      <p className="mb-1 text-[12px] text-ink-3">{quien}</p>
      <p className={`text-[15px] leading-relaxed ${destacada ? "text-ink" : "text-ink-2"}`}>{children}</p>
    </div>
  );
}

function Marca({
  ok,
  activa,
  etiqueta,
  onClick,
}: {
  ok?: boolean;
  activa: boolean;
  etiqueta: string;
  onClick: () => void;
}) {
  const color = ok ? "bg-live text-black border-live" : "bg-danger text-white border-danger";
  return (
    <button
      type="button"
      aria-label={etiqueta}
      aria-pressed={activa}
      onClick={onClick}
      className={`press grid size-11 shrink-0 place-items-center rounded-full border ${activa ? color : "border-line-strong text-ink-3"}`}
    >
      {ok ? <Check width={20} height={20} /> : <Close width={18} height={18} />}
    </button>
  );
}
