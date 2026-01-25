import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Hardcore Player",
  description: "Learning video factory with bilingual subtitles",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
