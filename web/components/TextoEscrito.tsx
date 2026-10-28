"use client";

import { useEffect, useState, useSyncExternalStore } from "react";

const MS_POR_PALABRA = 38;

/** A reply that appears word by word, like a chat AI typing. The text is already whole (checked by the
 *  guards on the server, which is why it isn't streamed token by token): only its reveal is animated.
 *  `animar` false (replies already on screen, reduced motion) shows it at once. */
export function TextoEscrito({
  texto,
  animar,
  alAvanzar,
}: {
  texto: string;
  animar: boolean;
  alAvanzar?: () => void;
}) {
  const quieto = useSyncExternalStore(suscribir, reducido, () => false);
  const partes = texto.split(/(\s+)/); // words and the spaces between them, so the layout doesn't jump
  const [visibles, setVisibles] = useState(animar ? 0 : partes.length);
  const completo = quieto || visibles >= partes.length;

  useEffect(() => {
    if (completo) return;
    const t = setInterval(() => {
      setVisibles((n) => n + 2); // a word and its space
      alAvanzar?.();
    }, MS_POR_PALABRA);
    return () => clearInterval(t);
  }, [completo, alAvanzar]);

  if (completo) return <>{texto}</>;
  return (
    <>
      <span>{partes.slice(0, visibles).join("")}</span>
      {/* the rest keeps its space, invisible: the bubble doesn't grow line by line */}
      <span aria-hidden className="invisible">
        {partes.slice(visibles).join("")}
      </span>
    </>
  );
}

const MQ = "(prefers-reduced-motion: reduce)";
const reducido = () => window.matchMedia(MQ).matches;
function suscribir(cb: () => void) {
  const mq = window.matchMedia(MQ);
  mq.addEventListener("change", cb);
  return () => mq.removeEventListener("change", cb);
}
