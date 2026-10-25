// Accent color the student picks in the user menu. The tokens live in app/globals.css under
// <html data-acento="...">; the choice is saved per user in the backend (/api/preferencias) and
// mirrored in a cookie so the server renders the right one on the first paint (app/layout.tsx).

export const ACENTOS = [
  { id: "menta", nombre: "Menta", color: "#6ee7d2" },
  { id: "rosa", nombre: "Rosa", color: "#ffb0d6" },
  { id: "gris", nombre: "Gris", color: "#c9cfd6" },
  { id: "azul", nombre: "Azul", color: "#90d8ff" },
] as const;

export type Acento = (typeof ACENTOS)[number]["id"];

export const ACENTO_POR_DEFECTO: Acento = "menta";
export const COOKIE_ACENTO = "chiron-acento";

export function esAcento(v: unknown): v is Acento {
  return ACENTOS.some((a) => a.id === v);
}

/** Applies the accent right away and remembers it in the cookie the server reads (client only). */
export function aplicarAcento(acento: Acento) {
  document.documentElement.dataset.acento = acento;
  const seguro = location.protocol === "https:" ? "; secure" : "";
  document.cookie = `${COOKIE_ACENTO}=${acento}; path=/; max-age=31536000; samesite=lax${seguro}`;
}
