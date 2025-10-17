import type { Metadata } from "next";
import "@/styles/globals.css";
import { Providers } from "./providers";
import { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Transcriptor de FERIA",
  description: "Panel local para transcribir y resumir reuniones",
  icons: [{ rel: "icon", url: "/favicon.ico" }]
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="es" className="dark">
      <body className="min-h-screen bg-zinc-950 text-zinc-100">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
