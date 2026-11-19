import type { Metadata } from "next";
import { EmailConfirmHashBridge } from "@/components/auth/email-confirm-hash-bridge";
import { HomeLanding } from "@/components/marketing/home-landing";
import { PublicStructuredData } from "@/components/marketing/structured-data";
import { AuthFormProviders } from "@/providers/auth-form-providers";

export const metadata: Metadata = {
  title: {
    absolute: "QuantForg — AI Gold Trading Robot for MT5 & AI Trading Assistant",
  },
  description:
    "QuantForg is an AI gold (XAUUSD) trading robot for MetaTrader 5 with QuantForg AI, an assistant that analyzes the live gold market and your chart screenshots. Risk limits on every trade, no martingale, your money stays at your broker. Start free.",
  alternates: { canonical: "/" },
  openGraph: {
    title: "QuantForg — AI Gold Trading Robot for MT5",
    description:
      "Connect your MT5 broker, analyze markets, manage risk, and execute under approved settings.",
    url: "/",
    images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "QuantForg" }],
  },
};

export default function LandingPage() {
  return (
    <AuthFormProviders>
      <EmailConfirmHashBridge />
      <PublicStructuredData />
      <HomeLanding />
    </AuthFormProviders>
  );
}
