"use client";

import { useCallback, useEffect, useSyncExternalStore } from "react";
import { toast } from "sonner";
import { api } from "./api";
import { MASCOTA_POR_DEFECTO, type MascotaId, esMascota } from "./mascotas";

// The student's pet: saved per user in the backend (/api/preferencias), with a copy in localStorage so
// it shows at once on the next visit (only a cache: the backend's value wins once it arrives).

const CLAVE = "chiron-mascota";
let actual: MascotaId | null = null;
let sincronizada = false;
const oyentes = new Set<() => void>();

function leerCache(): MascotaId {
  try {
    const v = localStorage.getItem(CLAVE);
    return esMascota(v) ? v : MASCOTA_POR_DEFECTO;
  } catch {
    return MASCOTA_POR_DEFECTO;
  }
}

function poner(id: MascotaId) {
  actual = id;
  try {
    localStorage.setItem(CLAVE, id);
  } catch {}
  oyentes.forEach((f) => f());
}

const suscribir = (f: () => void) => {
  oyentes.add(f);
  return () => oyentes.delete(f);
};
const leer = () => (actual ??= leerCache());

/** [the student's pet, a setter that saves it]. */
export function useMascota(): [MascotaId, (id: MascotaId) => void] {
  const id = useSyncExternalStore(suscribir, leer, () => MASCOTA_POR_DEFECTO);

  useEffect(() => {
    if (sincronizada) return; // once per page load
    sincronizada = true;
    api
      .preferencias()
      .then((p) => esMascota(p.mascota) && poner(p.mascota))
      .catch(() => {}); // the cached one (or the default) stays
  }, []);

  const elegir = useCallback((nueva: MascotaId) => {
    const anterior = leer();
    if (nueva === anterior) return;
    poner(nueva);
    api.guardarMascota(nueva).catch((e: Error) => {
      if (leer() !== nueva) return; // another one was picked meanwhile
      poner(anterior);
      toast.error(`No se pudo guardar la mascota. ${e.message}`, { id: "mascota" });
    });
  }, []);

  return [id, elegir];
}
