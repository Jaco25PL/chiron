import Image from "next/image";

/** Chiron mark (C + K). Source: docs/brand/logo-source.png; web/public/logo.png is the trimmed,
 *  transparent version. The favicon and Apple icon live in app/icon.png and app/apple-icon.png. */
export function Logo({ size = 26 }: { size?: number }) {
  return <Image src="/logo.png" alt="" width={size} height={size} priority aria-hidden />;
}
