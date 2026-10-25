"use client";

import { useEffect } from "react";
import { aplicarAcento, esAcento, type Acento } from "@/lib/acento";
import { api } from "@/lib/api";

const REVISADO = "chiron-acento-revisado";

/** Keeps the accent cookie in step with the backend. The server already rendered `acento` on
 *  <html>; this only (a) stores the cookie when the server had to ask the backend (new device),
 *  so later renders skip that call, and (b) once per tab, checks whether the color was changed on
 *  another device (the cookie here would be stale). Renders nothing. */
export function AcentoSync({ acento, origen }: { acento: Acento; origen: "cookie" | "backend" | "defecto" }) {
  useEffect(() => {
    if (origen === "backend") {
      aplicarAcento(acento);
      return;
    }
    if (origen !== "cookie") return;
    try {
      if (sessionStorage.getItem(REVISADO)) return;
      sessionStorage.setItem(REVISADO, "1");
    } catch {
      return; // no storage (private mode): don't ask on every page
    }
    api
      .preferencias()
      .then(({ acento: guardado }) => {
        // only if the student didn't pick another one meanwhile
        if (esAcento(guardado) && guardado !== acento && document.documentElement.dataset.acento === acento) {
          aplicarAcento(guardado);
        }
      })
      .catch(() => {}); // signed out or backend down: keep what the server rendered
  }, [acento, origen]);
  return null;
}
