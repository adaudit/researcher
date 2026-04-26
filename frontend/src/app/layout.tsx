import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Researcher — Creative Intelligence Platform",
  description: "AI-powered creative strategy that compounds",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
