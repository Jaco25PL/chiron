"use client";

import { useEffect, useRef, useState } from "react";
import { cerrarSesion } from "@/lib/actions";

export type Usuario = { nombre: string; email: string; imagen: string | null };

/** Avatar with a small popover (name, email, sign out). Origin anchored to the trigger. */
export function UserMenu({ usuario }: { usuario: Usuario }) {
  const [abierto, setAbierto] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!abierto) return;
    const cerrar = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !ref.current?.contains(e.target as Node)) setAbierto(false);
    };
    document.addEventListener("mousedown", cerrar);
    document.addEventListener("keydown", cerrar);
    return () => {
      document.removeEventListener("mousedown", cerrar);
      document.removeEventListener("keydown", cerrar);
    };
  }, [abierto]);

  const inicial = (usuario.nombre || usuario.email || "?")[0].toUpperCase();

  return (
    <div ref={ref} className="relative">
      <button
        aria-label="Cuenta"
        aria-expanded={abierto}
        onClick={() => setAbierto((a) => !a)}
        className="press grid size-9 place-items-center overflow-hidden rounded-full border border-line-strong bg-glass-strong text-sm font-medium"
      >
        {usuario.imagen ? (
          // eslint-disable-next-line @next/next/no-img-element -- avatar from Google, tiny and external
          <img src={usuario.imagen} alt="" referrerPolicy="no-referrer" className="size-full object-cover" />
        ) : (
          inicial
        )}
      </button>
      {abierto && (
        <div className="glass enter absolute right-0 top-11 z-30 w-64 origin-top-right rounded-2xl bg-bg-2/90 p-2">
          <div className="px-3 py-2.5">
            <p className="truncate text-sm font-medium">{usuario.nombre || "Sin nombre"}</p>
            <p className="truncate text-xs text-ink-3">{usuario.email}</p>
          </div>
          <form action={cerrarSesion}>
            <button className="press w-full rounded-xl px-3 py-2.5 text-left text-sm text-ink-2 hover:bg-glass-strong hover:text-ink">
              Cerrar sesión
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
