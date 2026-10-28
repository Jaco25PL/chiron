"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import { ANIMACIONES, CELDA, type Animacion, type MascotaId, mascota } from "@/lib/mascotas";

/** The study companion's pet: one animation of its sprite sheet (public/mascotas/<id>.webp), looping.
 *  `alto` is the height in CSS px. With reduced motion it shows the first frame and doesn't float. */
export function Mascota({
  id,
  animacion = "reposo",
  alto = 72,
  flotar = true,
  decorativa = false,
  className = "",
}: {
  id: MascotaId;
  animacion?: Animacion;
  alto?: number;
  flotar?: boolean;
  /** Next to its name (a label already says it): hidden from screen readers. */
  decorativa?: boolean;
  className?: string;
}) {
  const anim = ANIMACIONES[animacion];
  const quieta = useSyncExternalStore(suscribirMovimiento, movimientoReducido, () => false);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (quieta) return;
    const t = setInterval(() => {
      if (!document.hidden) setTick((n) => n + 1);
    }, anim.ms);
    return () => clearInterval(t);
  }, [anim.ms, quieta]);
  const frame = quieta ? 0 : tick % anim.frames;

  const escala = alto / CELDA.h;
  const ancho = Math.round(CELDA.w * escala);
  return (
    <span
      role={decorativa ? undefined : "img"}
      aria-label={decorativa ? undefined : mascota(id).nombre}
      aria-hidden={decorativa || undefined}
      className={`inline-block shrink-0 ${flotar && !quieta ? "flotar" : ""} ${className}`}
      style={{
        width: ancho,
        height: alto,
        backgroundImage: `url(/mascotas/${id}.webp)`,
        backgroundRepeat: "no-repeat",
        // the sheet is 6 cells wide and 5 rows tall (web/scripts/mascotas.py)
        backgroundSize: `${6 * ancho}px ${5 * alto}px`,
        backgroundPosition: `-${frame * ancho}px -${anim.fila * alto}px`,
      }}
    />
  );
}

const MQ = "(prefers-reduced-motion: reduce)";
const movimientoReducido = () => window.matchMedia(MQ).matches;
function suscribirMovimiento(cb: () => void) {
  const mq = window.matchMedia(MQ);
  mq.addEventListener("change", cb);
  return () => mq.removeEventListener("change", cb);
}
