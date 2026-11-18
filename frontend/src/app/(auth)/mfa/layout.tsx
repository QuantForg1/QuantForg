import type { Metadata } from "next";

export const metadata: Metadata = { title: "Verification code" };

export default function MfaLayout({ children }: { children: React.ReactNode }) {
  return children;
}