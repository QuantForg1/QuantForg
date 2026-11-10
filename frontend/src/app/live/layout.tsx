import type { Metadata } from "next";
import { PublicMarketProviders } from "@/providers/public-market-providers";

export const metadata: Metadata = {
  title: "Live Market",
  description:
    "Public QuantForg live market chart for XAUUSD. No login or personal broker connection required.",
  robots: { index: true, follow: true },
};

export default function LiveMarketLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <PublicMarketProviders>{children}</PublicMarketProviders>;
}
