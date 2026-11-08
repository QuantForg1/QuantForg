import { BILLING_PLANS } from "@/lib/billing/plans";

const SITE =
  process.env.NEXT_PUBLIC_APP_URL?.replace(/\/$/, "") || "https://www.quantforg.com";

/** Accurate Organization + SoftwareApplication JSON-LD (no fake ratings). */
export function PublicStructuredData() {
  const organization = {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: "QuantForg",
    url: SITE,
    logo: `${SITE}/brand/quantforg-mark.png`,
    email: "support@quantforg.com",
    sameAs: [] as string[],
  };

  const software = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "QuantForg",
    applicationCategory: "BusinessApplication",
    operatingSystem: "Web",
    url: SITE,
    description:
      "Trading technology platform for MetaTrader 5 workflows, risk controls, and operator desks. Software access only; trading outcomes are not guaranteed.",
    offers: BILLING_PLANS.map((plan) => ({
      "@type": "Offer",
      name: plan.name,
      price: String(plan.monthlyPriceUsd),
      priceCurrency: "USD",
      category: "Subscription",
      description: plan.positioning,
      url: `${SITE}/pricing`,
      availability: "https://schema.org/OnlineOnly",
    })),
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(organization) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(software) }}
      />
    </>
  );
}
