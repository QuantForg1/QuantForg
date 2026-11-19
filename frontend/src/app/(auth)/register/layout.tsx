import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Create your free account",
  description:
    "Create a free QuantForg account: connect your MT5 broker, try QuantForg AI market analysis and screenshot analysis, and switch on the AI gold trading robot when you subscribe.",
  alternates: { canonical: "/register" },
  robots: { index: true, follow: true },
};

export default function RegisterLayout({ children }: { children: React.ReactNode }) {
  return children;
}
