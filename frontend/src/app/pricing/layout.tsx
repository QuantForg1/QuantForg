import type { ReactNode } from "react";
import { AuthFormProviders } from "@/providers/auth-form-providers";

/** Auth-aware marketing chrome for pricing (Dashboard vs Sign In). */
export default function PricingLayout({ children }: { children: ReactNode }) {
  return <AuthFormProviders>{children}</AuthFormProviders>;
}
