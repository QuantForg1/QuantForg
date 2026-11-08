import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Contact",
  description: "Contact QuantForg sales and support about subscription access.",
  alternates: { canonical: "/contact" },
};

export default function ContactLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
