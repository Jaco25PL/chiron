"use client";

import { useState, useTransition } from "react";
import { toast } from "sonner";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ACENTO_POR_DEFECTO, ACENTOS, aplicarAcento, esAcento, type Acento } from "@/lib/acento";
import { cerrarSesion } from "@/lib/actions";
import { api } from "@/lib/api";

/** The accent on <html data-acento> (rendered by the server, or changed since by AcentoSync). */
function acentoActual(): Acento {
  const actual = typeof document === "undefined" ? undefined : document.documentElement.dataset.acento;
  return esAcento(actual) ? actual : ACENTO_POR_DEFECTO;
}

export type Usuario = { nombre: string; email: string; imagen: string | null };

/** Avatar with a menu (name, email, accent color, sign out). Origin anchored to the trigger. */
export function UserMenu({ usuario }: { usuario: Usuario }) {
  const [acento, setAcento] = useState<Acento>(acentoActual);
  // opened with the keyboard: no animation (Emil Kowalski: nothing animated on keyboard actions)
  const [porTeclado, setPorTeclado] = useState(false);
  const [saliendo, startSalir] = useTransition();

  const elegir = (valor: string) => {
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

  return (
    <DropdownMenu modal={false} onOpenChange={(abierto) => abierto && setAcento(acentoActual())}>
      <DropdownMenuTrigger
        aria-label="Cuenta"
        onPointerDown={() => setPorTeclado(false)}
        onKeyDown={() => setPorTeclado(true)}
        className="press grid size-9 place-items-center overflow-hidden rounded-full border border-line-strong bg-glass-strong text-sm font-medium"
      >
        {usuario.imagen ? (
          // eslint-disable-next-line @next/next/no-img-element -- avatar from Google, tiny and external
          <img src={usuario.imagen} alt="" referrerPolicy="no-referrer" className="size-full object-cover" />
        ) : (
          inicial
        )}
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="end"
        sideOffset={8}
        className={`w-64 ${porTeclado ? "data-open:animate-none data-closed:animate-none" : ""}`}
      >
        <div className="px-3 py-2.5">
          <p className="truncate text-sm font-medium">{usuario.nombre || "Sin nombre"}</p>
          <p className="truncate text-xs text-ink-3">{usuario.email}</p>
        </div>
        <DropdownMenuSeparator />
        <DropdownMenuLabel id="menu-color">Color</DropdownMenuLabel>
        <DropdownMenuRadioGroup aria-labelledby="menu-color" value={acento} onValueChange={elegir}>
          {ACENTOS.map((a) => (
            <DropdownMenuRadioItem
              key={a.id}
              value={a.id}
              // keep the menu open: you see the new color right away and can try another
              onSelect={(e) => e.preventDefault()}
              className="text-ink-2"
            >
              <span aria-hidden className="size-3 rounded-full ring-1 ring-white/15" style={{ background: a.color }} />
              {a.nombre}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem disabled={saliendo} onSelect={() => startSalir(() => cerrarSesion())} className="text-ink-2">
          Cerrar sesión
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
