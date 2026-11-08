import type { Metadata } from "next";
import { HomeLanding } from "@/components/marketing/home-landing";
import { PublicStructuredData } from "@/components/marketing/structured-data";

export const metadata: Metadata = {
  title: {
    absolute: "QuantForg — Trading Technology Platform",
  },
  description:
    "QuantForg is a subscription trading technology platform for MT5 workflows, risk controls, research, and operator desks. Software functionality is not a promise of trading profits.",
  alternates: { canonical: "/" },
};

export default function LandingPage() {
  return (
    <>
      <PublicStructuredData />
      <HomeLanding />
    </>
  );
}
