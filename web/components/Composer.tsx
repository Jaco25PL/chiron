"use client";

import { useRef, useState, type ReactNode } from "react";
import { ArrowUp } from "./icons";

// Generic on purpose: they fit any case without hinting at what to examine.
export const SUGERENCIAS = ["Le tomo los signos vitales", "Le voy a hacer el examen físico", "Solicito estudios"];

/** Message field: Enter sends, Shift+Enter adds a line. No animation (it is a keyboard action). */
export function Composer({
  onSend,
  disabled,
  placeholder = "Preguntale algo al paciente…",
  before,
  sugerencias = true,
}: {
  onSend: (text: string) => void;
  disabled?: boolean;
  placeholder?: string;
  before?: ReactNode;
  sugerencias?: boolean;
}) {
  const [text, setText] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  const send = () => {
    if (!text.trim() || disabled) return;
    onSend(text);
    setText("");
    if (ref.current) ref.current.style.height = "";
  };

  return (
    <div className="flex w-full flex-col gap-2">
      {sugerencias && (
        <div className="no-scrollbar -mx-1 flex gap-1.5 overflow-x-auto px-1">
          {SUGERENCIAS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => {
                setText(s);
                ref.current?.focus();
              }}
              className="press shrink-0 rounded-full border border-line px-3 py-1.5 text-xs text-ink-2 hover:border-line-strong hover:text-ink"
            >
              {s}
            </button>
          ))}
        </div>
      )}
      <div className="flex items-end gap-2">
        {before}
        <div className="glass flex min-h-12 flex-1 items-end rounded-[26px] py-1.5 pl-4 pr-1.5 transition-colors focus-within:border-line-strong focus-within:bg-glass-strong">
          <textarea
            ref={ref}
            id="mensaje"
            rows={1}
            value={text}
            placeholder={placeholder}
            onChange={(e) => {
              setText(e.target.value);
              e.target.style.height = "auto";
              e.target.style.height = `${Math.min(e.target.scrollHeight, 140)}px`;
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                send();
              }
            }}
            className="max-h-[140px] flex-1 resize-none bg-transparent py-2 text-[16px] leading-6 text-ink outline-none placeholder:text-ink-3"
          />
          <button
            type="button"
            aria-label="Enviar"
            onClick={send}
            disabled={disabled || !text.trim()}
            className="press grid size-9 shrink-0 place-items-center rounded-full bg-accent text-accent-ink disabled:bg-glass-strong disabled:text-ink-3"
          >
            <ArrowUp width={18} height={18} strokeWidth={2.25} />
          </button>
        </div>
      </div>
    </div>
  );
}
