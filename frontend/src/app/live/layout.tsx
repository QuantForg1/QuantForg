import type { Metadata } from "next";
import { PublicMarketProviders } from "@/providers/public-market-providers";

export const metadata: Metadata = {
  title: "Live Gold Price Chart (XAUUSD)",
  description:
    "Free live gold price chart (XAUUSD) with real-time candles on every timeframe from M1 to D1. No login required.",
  alternates: { canonical: "/live" },
  robots: { index: true, follow: true },
};

export default function LiveMarketLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <PublicMarketProviders>{children}</PublicMarketProviders>;
}
