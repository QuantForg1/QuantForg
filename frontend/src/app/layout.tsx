import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import localFont from "next/font/local";
import "./globals.css";

/**
 * Self-hosted IBM Plex (latin) — avoids next/font/google fetch failures on Vercel
 * and keeps CSP font-src on 'self'. Display headings reuse --font-sans via
 * --font-display alias in globals.css.
 */
const sans = localFont({
  src: [
    { path: "../fonts/IBMPlexSans-Regular.woff2", weight: "400", style: "normal" },
    { path: "../fonts/IBMPlexSans-Medium.woff2", weight: "500", style: "normal" },
    { path: "../fonts/IBMPlexSans-SemiBold.woff2", weight: "600", style: "normal" },
  ],
  variable: "--font-sans",
  display: "swap",
  preload: true,
});

const mono = localFont({
  src: [
    { path: "../fonts/IBMPlexMono-Regular.woff2", weight: "400", style: "normal" },
    { path: "../fonts/IBMPlexMono-Medium.woff2", weight: "500", style: "normal" },
  ],
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
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#061B35" },
    { media: "(prefers-color-scheme: light)", color: "#061B35" },
  ],
  colorScheme: "dark",
};

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "QuantForg — Institutional AI Trading Platform",
    template: "%s · QuantForg",
  },
  description:
    "QuantForg connects traders to MetaTrader 5 broker accounts with market intelligence, strategy evaluation, risk management, and automated execution under approved settings. Software access only — trading outcomes are not guaranteed.",
  applicationName: "QuantForg",
  authors: [{ name: "QuantForg" }],
  creator: "QuantForg",
  publisher: "QuantForg",
  keywords: [
    "QuantForg",
    "institutional AI trading",
    "MT5",
    "Weltrade",
    "XAUUSD",
    "trading SaaS",
    "risk management",
    "automated trading software",
  ],
  alternates: {
    canonical: SITE_URL,
  },
  manifest: "/manifest.webmanifest",
  icons: {
    icon: [
      { url: "/favicon.svg", type: "image/svg+xml" },
      { url: "/favicon-32x32.png", type: "image/png", sizes: "32x32" },
      { url: "/favicon-16x16.png", type: "image/png", sizes: "16x16" },
      { url: "/favicon-48x48.png", type: "image/png", sizes: "48x48" },
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
    title: "QuantForg — Institutional AI Trading Platform",
    description:
      "Connect your MT5 broker, analyze markets, manage risk, and execute under approved settings. No profit guarantees.",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "QuantForg — Institutional AI Trading Platform",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "QuantForg — Institutional AI Trading Platform",
    description:
      "Institutional AI trading software for MT5 workflows, market intelligence, and risk-aware execution. Software access only.",
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
        className={`${sans.variable} ${mono.variable} antialiased`}
      >
        <a href="#main-content" className="qf-skip-link">
          Skip to content
        </a>
        {children}
      </body>
    </html>
  );
}
