// 1.75px line icons, SF Symbols style. They inherit the text color.
import type { SVGProps } from "react";

type P = SVGProps<SVGSVGElement>;
const base = (p: P) => ({
  width: 20,
  height: 20,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.75,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
  ...p,
});

export const ChevronLeft = (p: P) => (
  <svg {...base(p)}><path d="m15 18-6-6 6-6" /></svg>
);
export const ArrowUp = (p: P) => (
  <svg {...base(p)}><path d="M12 19V5M5 12l7-7 7 7" /></svg>
);
export const Chat = (p: P) => (
  <svg {...base(p)}><path d="M21 12a8 8 0 0 1-11.7 7.1L4 20l1-4.3A8 8 0 1 1 21 12Z" /></svg>
);
export const Video = (p: P) => (
  <svg {...base(p)}><rect x="2.5" y="6" width="13" height="12" rx="3" /><path d="m15.5 10.5 6-3.5v10l-6-3.5" /></svg>
);
export const Mic = (p: P) => (
  <svg {...base(p)}><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" /></svg>
);
export const CameraOff = (p: P) => (
  <svg {...base(p)}><path d="m3 3 18 18M15.5 10.5l6-3.5v10l-2.3-1.3M10 6h3.5a2 2 0 0 1 2 2v3M15.5 15.5V16a2 2 0 0 1-2 2h-9a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h1" /></svg>
);
export const PhoneDown = (p: P) => (
  <svg {...base(p)}><path d="M3.5 14.5c4.7-4.7 12.3-4.7 17 0l-1.8 2.3a1.4 1.4 0 0 1-1.8.3l-2.3-1.4a1.4 1.4 0 0 1-.6-1.4l.2-1.3a11 11 0 0 0-4.4 0l.2 1.3a1.4 1.4 0 0 1-.6 1.4l-2.3 1.4a1.4 1.4 0 0 1-1.8-.3Z" /></svg>
);
export const Stethoscope = (p: P) => (
  <svg {...base(p)}><path d="M5 3v5a5 5 0 0 0 10 0V3M10 13v2a5 5 0 0 0 10 0v-2" /><circle cx="20" cy="11" r="2" /></svg>
);
export const Clock = (p: P) => (
  <svg {...base(p)}><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></svg>
);
export const Close = (p: P) => (
  <svg {...base(p)}><path d="M18 6 6 18M6 6l12 12" /></svg>
);
