import type { Metadata } from "next";
import { HomeLanding } from "@/components/marketing/home-landing";
import { PublicStructuredData } from "@/components/marketing/structured-data";
import { AuthFormProviders } from "@/providers/auth-form-providers";

export const metadata: Metadata = {
  title: {
    absolute: "QuantForg — Institutional AI Trading Platform",
  },
  description:
    "QuantForg connects traders to MetaTrader 5 broker accounts with market intelligence, strategy evaluation, risk management, and automated execution under approved settings. Software access is not a promise of trading profits.",
  alternates: { canonical: "/" },
  openGraph: {
    title: "QuantForg — Institutional AI Trading Platform",
    description:
      "Connect your MT5 broker, analyze markets, manage risk, and execute under approved settings.",
    url: "/",
    images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "QuantForg" }],
  },
};

export default function LandingPage() {
  return (
    <AuthFormProviders>
      <PublicStructuredData />
      <HomeLanding />
    </AuthFormProviders>
  );
}
