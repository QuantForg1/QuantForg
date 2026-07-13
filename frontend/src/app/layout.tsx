import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Manrope, Sora } from "next/font/google";
import "./globals.css";

const sans = Manrope({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
  preload: true,
});

const display = Sora({
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
  preload: false,
});

export const metadata: Metadata = {
  title: {
    default: "QuantForg",
    template: "%s · QuantForg",
  },
  description:
    "Enterprise quantitative trading terminal — portfolio, risk, MT5, and research.",
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000",
  ),
  applicationName: "QuantForg",
  robots: {
    index: true,
    follow: true,
  },
  openGraph: {
    title: "QuantForg",
    description:
      "Enterprise quantitative trading terminal — portfolio, risk, MT5, and research.",
    type: "website",
    siteName: "QuantForg",
  },
  twitter: {
    card: "summary",
    title: "QuantForg",
    description:
      "Enterprise quantitative trading terminal — portfolio, risk, MT5, and research.",
  },
};

export default function RootLayout({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className={`${sans.variable} ${display.variable} antialiased`}>
        <a href="#main-content" className="qf-skip-link">
          Skip to content
        </a>
        {children}
      </body>
    </html>
  );
}
