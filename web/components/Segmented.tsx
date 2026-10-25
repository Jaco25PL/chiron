"use client";

import { motion } from "motion/react";
import type { ReactNode } from "react";

type Option<T extends string> = { value: T; label: ReactNode; disabled?: boolean; hint?: string };

/** iOS-style segmented control: the pill slides between options (morph = ease-in-out). */
export function Segmented<T extends string>({
  value,
  onChange,
  options,
  id,
  size = "md",
}: {
  value: T;
  onChange: (v: T) => void;
  options: Option<T>[];
  id: string;
  size?: "sm" | "md";
}) {
  return (
    <div role="tablist" className="glass relative inline-flex rounded-full p-1">
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            role="tab"
            aria-selected={active}
            disabled={o.disabled}
            title={o.hint}
            onClick={() => onChange(o.value)}
            className={`press relative z-0 flex items-center gap-1.5 rounded-full font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
              size === "sm" ? "h-8 px-3 text-[13px]" : "h-9 px-4 text-sm"
            } ${active ? "text-bg" : "text-ink-2 hover:text-ink"}`}
          >
            {active && (
              <motion.span
                layoutId={`seg-${id}`}
                className="absolute inset-0 -z-10 rounded-full bg-ink"
                transition={{ type: "spring", duration: 0.35, bounce: 0.15 }}
              />
            )}
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
