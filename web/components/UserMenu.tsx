"use client";

import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { ACENTO_POR_DEFECTO, ACENTOS, aplicarAcento, esAcento, type Acento } from "@/lib/acento";
import { cerrarSesion } from "@/lib/actions";
import { api } from "@/lib/api";
import { MASCOTAS } from "@/lib/mascotas";
import { useMascota } from "@/lib/useMascota";
import { Mascota } from "./Mascota";

/** The accent on <html data-acento> (rendered by the server, or changed since by AcentoSync). */
function acentoActual(): Acento {
  const actual = typeof document === "undefined" ? undefined : document.documentElement.dataset.acento;
  return esAcento(actual) ? actual : ACENTO_POR_DEFECTO;
}

export type Usuario = { nombre: string; email: string; imagen: string | null };

/** The avatar opens the settings as a side sheet (like the history): who you are, accent color, the
 *  study companion's pet, sign out. Every choice applies at once and is saved per user. */
export function UserMenu({ usuario }: { usuario: Usuario }) {
  const [acento, setAcento] = useState<Acento>(acentoActual);
  const [mascotaId, elegirMascota] = useMascota();
  const [saliendo, startSalir] = useTransition();

  const elegirAcento = (valor: string) => {
    if (!esAcento(valor) || valor === acento) return;
    const anterior = acento;
    setAcento(valor);
    aplicarAcento(valor); // instant, and the cookie makes the next server render match
    api.guardarAcento(valor).catch((e: Error) => {
      if (acentoActual() !== valor) return; // another color was picked meanwhile
      setAcento(anterior);
      aplicarAcento(anterior);
      toast.error(`No se pudo guardar el color. ${e.message}`, { id: "acento" });
    });
  };

  const inicial = (usuario.nombre || usuario.email || "?")[0].toUpperCase();
  const avatar = usuario.imagen ? (
    // eslint-disable-next-line @next/next/no-img-element -- avatar from Google, tiny and external
    <img src={usuario.imagen} alt="" referrerPolicy="no-referrer" className="size-full object-cover" />
  ) : (
    inicial
  );

  return (
    <Sheet onOpenChange={(abierto) => abierto && setAcento(acentoActual())}>
      <SheetTrigger
        aria-label="Cuenta"
        className="press grid size-9 place-items-center overflow-hidden rounded-full border border-line-strong bg-glass-strong text-sm font-medium"
      >
        {avatar}
      </SheetTrigger>
      <SheetContent className="w-full gap-0 overflow-y-auto sm:max-w-md">
        <SheetHeader className="px-5 pb-2 pt-5">
          <SheetTitle className="text-lg font-semibold tracking-tight">Ajustes</SheetTitle>
          <SheetDescription className="text-[13px] text-ink-3">Se guardan en tu cuenta.</SheetDescription>
        </SheetHeader>

        <div className="flex flex-col gap-7 px-5 pb-8 pt-3">
          <div className="flex items-center gap-3">
            <span className="grid size-11 shrink-0 place-items-center overflow-hidden rounded-full border border-line-strong bg-glass-strong text-base font-medium">
              {avatar}
            </span>
            <div className="min-w-0">
              <p className="truncate text-[15px] font-medium">{usuario.nombre || "Sin nombre"}</p>
              <p className="truncate text-[13px] text-ink-3">{usuario.email}</p>
            </div>
          </div>

          <fieldset>
            <legend className="mb-3 text-[13px] font-medium text-ink-2">Color</legend>
            <div className="flex flex-wrap gap-2">
              {ACENTOS.map((a) => (
                <label
                  key={a.id}
                  className="press flex h-9 cursor-pointer items-center gap-2 rounded-full border border-line-strong bg-glass px-3.5 text-[13px] text-ink-2 has-[:checked]:border-accent has-[:checked]:text-ink has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-accent"
                >
                  <input
                    type="radio"
                    name="acento"
                    value={a.id}
                    checked={acento === a.id}
                    onChange={(e) => elegirAcento(e.target.value)}
                    className="sr-only"
                  />
                  <span aria-hidden className="size-3 rounded-full ring-1 ring-white/15" style={{ background: a.color }} />
                  {a.nombre}
                </label>
              ))}
            </div>
          </fieldset>

          <fieldset>
            <legend className="mb-1 text-[13px] font-medium text-ink-2">Tu compañera de estudio</legend>
            <p className="mb-3 text-[12.5px] leading-snug text-ink-3">
              En la consulta, tocala para preguntarle una duda: te ayuda con los apuntes del curso y el paciente no se
              entera.
            </p>
            <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
              {MASCOTAS.map((m) => (
                <label
                  key={m.id}
                  className="press flex cursor-pointer flex-col items-center gap-1 rounded-2xl border border-line bg-glass px-1 pb-2 pt-2.5 text-[12px] text-ink-2 has-[:checked]:border-accent has-[:checked]:bg-accent/10 has-[:checked]:text-ink has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-accent"
                >
                  <input
                    type="radio"
                    name="mascota"
                    value={m.id}
                    checked={mascotaId === m.id}
                    onChange={() => elegirMascota(m.id)}
                    className="sr-only"
                  />
                  <Mascota
                    id={m.id}
                    animacion={mascotaId === m.id ? "salto" : "reposo"}
                    alto={56}
                    flotar={false}
                    decorativa
                  />
                  {m.nombre}
                </label>
              ))}
            </div>
            <p className="mt-3 text-[11.5px] leading-snug text-ink-3">
              Mascotas de{" "}
              <a href="https://petdex.dev" target="_blank" rel="noreferrer" className="underline hover:text-ink-2">
                Petdex
              </a>
              , por {[...new Set(MASCOTAS.map((m) => m.autor))].join(", ")} (licencias libres, CC BY-SA).
            </p>
          </fieldset>

          <button
            type="button"
            disabled={saliendo}
            onClick={() => startSalir(() => cerrarSesion())}
            className="press h-10 rounded-full border border-line-strong bg-glass text-[14px] text-ink-2 hover:text-ink disabled:opacity-40"
          >
            Cerrar sesión
          </button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
