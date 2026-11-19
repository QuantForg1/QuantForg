import type { Metadata } from "next";
import { PublicMarketProviders } from "@/providers/public-market-providers";

export const metadata: Metadata = {
  title: "Live Gold Price Chart (XAUUSD)",
  description:
    "Free live gold price chart (XAUUSD) with real-time candles on every timeframe from M1 to D1. No login required.",
  alternates: { canonical: "/live" },
  robots: { index: true, follow: true },
  openGraph: {
    title: "QuantForg Live Market — XAUUSD",
    description:
      "Public gold (XAUUSD) chart. No login or personal broker connection required. A chart is not an order.",
    url: "/live",
    images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "QuantForg" }],
  },
};

export default function LiveMarketLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <PublicMarketProviders>{children}</PublicMarketProviders>;
}
