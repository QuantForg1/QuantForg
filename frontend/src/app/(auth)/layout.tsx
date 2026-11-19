import type { Metadata } from "next";
import { AuthFormProviders } from "@/providers/auth-form-providers";

export const metadata: Metadata = {
  title: {
    template: "%s · QuantForg",
    default: "Sign in",
  },
  description:
    "Sign in to QuantForg, the AI gold trading robot for MetaTrader 5 with QuantForg AI market analysis.",
  // Only /login and /register are indexable (they set their own canonical).
  robots: { index: false, follow: true },
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
