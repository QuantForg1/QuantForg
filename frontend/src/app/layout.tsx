import type { Metadata } from "next";
import type { ReactNode } from "react";
import { IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";
import "./globals.css";

const sans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-sans",
  display: "swap",
  preload: true,
});

const display = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["500", "600"],
  variable: "--font-display",
  display: "swap",
  preload: false,
});

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
  display: "swap",
  preload: true,
});

export const metadata: Metadata = {
  title: {
    default: "QuantForg",
    template: "%s · QuantForg",
  },
  description:
    "Institutional trading operating system — terminal, book, research, and counsel.",
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_APP_URL ||
      (process.env.VERCEL_URL
        ? `https://${process.env.VERCEL_URL.replace(/^https?:\/\//, "")}`
        : process.env.NODE_ENV === "production"
          ? "https://www.quantforg.com"
          : "http://localhost:3000"),
  ),
  applicationName: "QuantForg",
  robots: {
    index: true,
    follow: true,
  },
  openGraph: {
    title: "QuantForg",
    description:
      "Institutional trading operating system — terminal, book, research, and counsel.",
    type: "website",
    siteName: "QuantForg",
  },
  twitter: {
    card: "summary",
    title: "QuantForg",
    description:
      "Institutional trading operating system — terminal, book, research, and counsel.",
  },
};

export default function RootLayout({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body
        className={`${sans.variable} ${display.variable} ${mono.variable} antialiased`}
      >
        <a href="#main-content" className="qf-skip-link">
          Skip to content
        </a>
        {children}
      </body>
    </html>
  );
}
