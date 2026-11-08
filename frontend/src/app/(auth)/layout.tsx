import type { Metadata } from "next";
import { AuthFormProviders } from "@/providers/auth-form-providers";

export const metadata: Metadata = {
  title: {
    template: "%s · QuantForg",
    default: "Sign in",
  },
  description:
    "Sign in to QuantForg — Institutional AI Trading Platform for MetaTrader 5 connectivity, market intelligence, and risk-aware execution.",
  robots: { index: true, follow: true },
  openGraph: {
    images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "QuantForg" }],
  },
};

export default function AuthGroupLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AuthFormProviders>{children}</AuthFormProviders>;
}
