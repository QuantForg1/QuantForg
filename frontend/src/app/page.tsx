import type { Metadata } from "next";
import { HomeLanding } from "@/components/marketing/home-landing";
import { PublicStructuredData } from "@/components/marketing/structured-data";
import { AuthFormProviders } from "@/providers/auth-form-providers";

export const metadata: Metadata = {
  title: {
    absolute: "QuantForg — Institutional AI Trading Platform",
  },
  description:
    "QuantForg connects your MT5 trading account to institutional market intelligence, strategy analysis and risk controls — keeping your capital and broker account under your control. Software access is not a promise of trading profits.",
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
