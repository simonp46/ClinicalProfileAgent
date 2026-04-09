import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Respiro Integral | Copiloto Clinico",
  description: "Copiloto de documentacion clinica para terapeutas de Respiro Integral",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es">
      <body className="font-sans">{children}</body>
    </html>
  );
}
