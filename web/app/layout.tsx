import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { cookies } from "next/headers";
import { Toaster } from "sonner";
import { auth } from "@/auth";
import { AcentoSync } from "@/components/AcentoSync";
import { ACENTO_POR_DEFECTO, COOKIE_ACENTO, esAcento, type Acento } from "@/lib/acento";
import { backendFetch } from "@/lib/backend";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Chiron",
  description: "Practicá el ECOE con pacientes virtuales.",
};

export const viewport: Viewport = {
  themeColor: "#050607",
  viewportFit: "cover",
};

/** The student's accent color, resolved on the server so the first paint already has it (no
 *  mint-then-switch flash). The cookie makes it free; without one (a new device, or after signing
 *  out) it asks the backend, briefly. Signed out, or backend slow or down: the default. */
async function acentoInicial(): Promise<{ acento: Acento; origen: "cookie" | "backend" | "defecto" }> {
  const guardado = (await cookies()).get(COOKIE_ACENTO)?.value;
  if (esAcento(guardado)) return { acento: guardado, origen: "cookie" };
  try {
    const usuario = (await auth())?.user;
    if (usuario?.email) {
      const res = await backendFetch(
        "/api/preferencias",
        { email: usuario.email, nombre: usuario.name },
        { signal: AbortSignal.timeout(2000) },
      );
      const { acento } = await res.json();
      if (res.ok && esAcento(acento)) return { acento, origen: "backend" };
    }
  } catch {
    // backend down, cold and slow, or not configured
  }
  return { acento: ACENTO_POR_DEFECTO, origen: "defecto" };
}

export default async function RootLayout({ children }: LayoutProps<"/">) {
  const { acento, origen } = await acentoInicial();
  return (
    <html lang="es" data-acento={acento} className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="min-h-dvh">
        {children}
        <AcentoSync acento={acento} origen={origen} />
        <Toaster theme="dark" position="top-center" toastOptions={{ className: "!rounded-2xl" }} />
      </body>
    </html>
  );
}
