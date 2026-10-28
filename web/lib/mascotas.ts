// The study companion's pets (components/Mascota.tsx). From Petdex (https://petdex.dev), only pets
// whose author declared a license that allows reuse (CC0, CC-BY or CC-BY-SA; we treat them as CC-BY-SA:
// credited in the settings, and a modified sprite keeps that license). Sheets built by
// web/scripts/mascotas.py; the ids match store/db.py MASCOTAS.

export const MASCOTAS = [
  { id: "scarf-hamster", nombre: "Hámster", autor: "indigocloud6" },
  { id: "boba", nombre: "Boba", autor: "railly" },
  { id: "cache-capy", nombre: "Capi", autor: "railly" },
  { id: "rocky-4", nombre: "Rocky", autor: "Ken H." },
  { id: "byte-bunny", nombre: "Conejita", autor: "railly" },
  { id: "pixel-panda", nombre: "Panda", autor: "railly" },
  { id: "prompt-penguin", nombre: "Pingüino", autor: "railly" },
  { id: "chedarini", nombre: "Chedarini", autor: "railly" },
  { id: "sunny", nombre: "Sunny", autor: "railly" },
  { id: "boxcat", nombre: "Gato en caja", autor: "railly" },
] as const;

export type MascotaId = (typeof MASCOTAS)[number]["id"];
export const MASCOTA_POR_DEFECTO: MascotaId = "scarf-hamster";

export function esMascota(v: unknown): v is MascotaId {
  return MASCOTAS.some((m) => m.id === v);
}

export function mascota(id: MascotaId) {
  return MASCOTAS.find((m) => m.id === id) ?? MASCOTAS[0];
}

/** One cell of the sheet (2/3 of Petdex's 192x208). */
export const CELDA = { w: 128, h: 139 };

/** Rows of each sheet, in this order (web/scripts/mascotas.py ROWS): frames and ms per frame, from Petdex. */
export const ANIMACIONES = {
  reposo: { fila: 0, frames: 6, ms: 183 }, // idle
  saludo: { fila: 1, frames: 4, ms: 175 }, // waving: while it talks
  revisando: { fila: 2, frames: 6, ms: 171 }, // review (writes, reads): while it thinks
  salto: { fila: 3, frames: 5, ms: 168 }, // jumping: just opened, happy
  esperando: { fila: 4, frames: 6, ms: 168 }, // waiting: listening to the student
} as const;

export type Animacion = keyof typeof ANIMACIONES;
