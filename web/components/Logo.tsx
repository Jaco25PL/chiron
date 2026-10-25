export function Logo({ size = 26 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden>
      <circle cx="16" cy="16" r="15" fill="none" stroke="var(--accent)" strokeOpacity=".35" />
      <path d="M21 10.5a7.5 7.5 0 1 0 0 11" fill="none" stroke="var(--accent)" strokeWidth="2.4" strokeLinecap="round" />
    </svg>
  );
}
