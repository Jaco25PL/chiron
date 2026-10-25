import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Toaster } from "sonner";
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

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="es" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="min-h-dvh">
        {children}
        <Toaster theme="dark" position="top-center" toastOptions={{ className: "!rounded-2xl" }} />
      </body>
    </html>
  );
}
