import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Contact",
  description:
    "Contact QuantForg about Institutional AI Trading Platform access, Weltrade / MT5 connectivity, and subscription options. Software access only — trading outcomes are not guaranteed.",
  alternates: { canonical: "/contact" },
  openGraph: {
    title: "Contact QuantForg",
    description:
      "Talk with QuantForg about platform access and broker connectivity.",
    url: "/contact",
    images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "QuantForg" }],
  },
};

export default function ContactLayout({ children }: { children: ReactNode }) {
  return children;
}
