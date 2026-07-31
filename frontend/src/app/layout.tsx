import type { Metadata, Viewport } from "next";
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

const SITE_URL =
  process.env.NEXT_PUBLIC_APP_URL ||
  (process.env.VERCEL_URL
    ? `https://${process.env.VERCEL_URL.replace(/^https?:\/\//, "")}`
    : process.env.NODE_ENV === "production"
      ? "https://www.quantforg.com"
      : "http://localhost:3000");

export const viewport: Viewport = {
  themeColor: "#00D4E0",
  colorScheme: "dark",
};

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "QuantForg — Institutional Trading OS",
    template: "%s · QuantForg",
  },
  description:
    "Institutional trading terminal for operators who demand clarity. Live MT5 portfolio sync, risk before fill, research loop, and AI workspace — one operating system.",
  applicationName: "QuantForg",
  authors: [{ name: "QuantForg" }],
  creator: "QuantForg",
  publisher: "QuantForg",
  keywords: [
    "QuantForg",
    "institutional trading",
    "MT5",
    "trading terminal",
    "portfolio risk",
    "algorithmic trading",
  ],
  manifest: "/manifest.webmanifest",
  icons: {
    icon: [
      { url: "/favicon-32x32.png", type: "image/png", sizes: "32x32" },
      { url: "/favicon-16x16.png", type: "image/png", sizes: "16x16" },
      { url: "/icon-192.png", type: "image/png", sizes: "192x192" },
      { url: "/icon-512.png", type: "image/png", sizes: "512x512" },
      { url: "/favicon.ico", sizes: "any" },
    ],
    shortcut: ["/favicon.ico"],
    apple: [{ url: "/apple-touch-icon.png", sizes: "180x180", type: "image/png" }],
  },
  openGraph: {
    type: "website",
    locale: "en_US",
    url: SITE_URL,
    siteName: "QuantForg",
    title: "QuantForg — Institutional Trading OS",
    description:
      "Institutional trading terminal for operators who demand clarity. Live MT5 portfolio, risk before fill, research, and AI — one operating system.",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "QuantForg — Institutional Trading OS",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "QuantForg — Institutional Trading OS",
    description:
      "Institutional trading terminal for operators who demand clarity. Live MT5 portfolio, risk before fill, research, and AI.",
    images: ["/og-image.png"],
  },
  robots: {
    index: true,
    follow: true,
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
