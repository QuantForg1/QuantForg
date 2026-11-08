import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";
import "./globals.css";

/**
 * One IBM Plex Sans loader only. Turbopack fails production builds when the
 * same next/font/google family is instantiated twice ("queries have exactly
 * one entry" / missing @vercel/turbopack-next font resolver). Display headings
 * reuse --font-sans via --font-display alias in globals.css.
 */
const sans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-sans",
  display: "swap",
  preload: true,
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
  themeColor: "#111827",
  colorScheme: "dark",
};

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "QuantForg — Trading Technology Platform",
    template: "%s · QuantForg",
  },
  description:
    "QuantForg is a trading technology SaaS platform for MT5 workflows, risk controls, research, and operator desks. Software access only — trading outcomes are not guaranteed.",
  applicationName: "QuantForg",
  authors: [{ name: "QuantForg" }],
  creator: "QuantForg",
  publisher: "QuantForg",
  keywords: [
    "QuantForg",
    "trading technology",
    "MT5",
    "trading SaaS",
    "risk management",
    "algorithmic trading software",
  ],
  alternates: {
    canonical: SITE_URL,
  },
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
    title: "QuantForg — Trading Technology Platform",
    description:
      "Subscription trading technology for MT5 workflows, risk controls, and operator desks. No profit guarantees.",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "QuantForg — Trading Technology Platform",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "QuantForg — Trading Technology Platform",
    description:
      "Trading technology SaaS for MT5 workflows and risk-aware operator desks. Software access only.",
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
