import type { Metadata } from "next";
import { PublicMarketProviders } from "@/providers/public-market-providers";

export const metadata: Metadata = {
  title: "Live Track Record · QuantForg Gold Robot",
  description:
    "Every closed XAUUSD trade from the QuantForg robot, wins and losses, with no filtering. Read the real results before you decide.",
  alternates: { canonical: "/performance" },
  robots: { index: true, follow: true },
};

export default function PerformanceLayout({ children }: { children: React.ReactNode }) {
  return <PublicMarketProviders>{children}</PublicMarketProviders>;
}
