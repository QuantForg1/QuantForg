import type { Metadata } from "next";
import { AuthFormProviders } from "@/providers/auth-form-providers";

export const metadata: Metadata = {
  robots: { index: false, follow: false },
};

/**
 * Billing checkout/return/invoices require AuthProvider so useAuth() does not crash
 * outside the authenticated app shell. Session is preserved across provider redirects.
 */
export default function BillingLayout({ children }: { children: React.ReactNode }) {
  return <AuthFormProviders>{children}</AuthFormProviders>;
}
