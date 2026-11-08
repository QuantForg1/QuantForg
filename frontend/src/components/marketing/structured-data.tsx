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
    image: `${SITE}/og-image.png`,
    email: "support@quantforg.com",
    description:
      "Institutional AI Trading Platform for MetaTrader 5 connectivity, market intelligence, risk management, and automated execution under approved settings.",
    sameAs: [] as string[],
  };

  const website = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: "QuantForg",
    url: SITE,
    description:
      "Institutional AI Trading Platform — connect your broker, analyze markets, manage risk, and execute under approved settings.",
    publisher: {
      "@type": "Organization",
      name: "QuantForg",
      logo: `${SITE}/brand/quantforg-mark.png`,
    },
  };

  const software = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "QuantForg",
    applicationCategory: "FinanceApplication",
    operatingSystem: "Web",
    url: SITE,
    description:
      "Institutional AI Trading Platform for MetaTrader 5 workflows, market intelligence, risk controls, and operator desks. Software access only; trading outcomes are not guaranteed.",
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
        dangerouslySetInnerHTML={{ __html: JSON.stringify(website) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(software) }}
      />
    </>
  );
}
