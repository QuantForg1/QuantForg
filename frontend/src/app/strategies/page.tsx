import type { Metadata } from "next";
import Link from "next/link";
import { PricingFooter, PricingHeader, pricingBtnPrimary, pricingBtnSecondary } from "@/components/pricing/marketing-chrome";
import { AuthFormProviders } from "@/providers/auth-form-providers";
import { SITE_URL, STRATEGIES, categoryGuide, strategiesByCategory } from "@/lib/seo/strategy-content";

export const metadata: Metadata = {
  title: { absolute: "Gold Trading Strategies: 100+ XAUUSD Strategies Explained · QuantForg" },
  description: `Learn 100+ gold (XAUUSD) trading strategies: trend, breakout, momentum, mean reversion, price action, sessions and key levels. Each one is explained in plain language and tested on real gold data by QuantForg.`,
  alternates: { canonical: "/strategies" },
  openGraph: {
    title: "100+ Gold Trading Strategies Explained",
    description: "Every major XAUUSD trading strategy explained, with when it works and when to avoid it.",
    url: "/strategies",
    images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "QuantForg gold trading strategies" }],
  },
};

export default function StrategiesHub() {
  const groups = strategiesByCategory();
  const jsonLd = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "CollectionPage",
        name: "Gold trading strategies",
        url: `${SITE_URL}/strategies`,
        description: metadata.description,
      },
      {
        "@type": "ItemList",
        numberOfItems: STRATEGIES.length,
        itemListElement: STRATEGIES.map((s, i) => ({
          "@type": "ListItem",
          position: i + 1,
          url: `${SITE_URL}/strategies/${s.slug}`,
          name: s.name,
        })),
      },
      {
        "@type": "BreadcrumbList",
        itemListElement: [
          { "@type": "ListItem", position: 1, name: "Home", item: SITE_URL },
          { "@type": "ListItem", position: 2, name: "Strategies", item: `${SITE_URL}/strategies` },
        ],
      },
    ],
  };

  return (
    <AuthFormProviders>
      <div className="relative min-h-screen bg-[var(--bg)] text-[var(--fg)]">
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
        <PricingHeader active="home" />
        <main id="main-content" tabIndex={-1} className="mx-auto max-w-6xl px-4 pb-16 pt-12 sm:px-6">
          <nav aria-label="Breadcrumb" className="text-xs text-[var(--fg-subtle)]">
            <Link href="/" className="hover:text-[var(--fg)]">Home</Link> / <span>Strategies</span>
          </nav>
          <header className="mt-4 max-w-3xl">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--accent)]">Strategy library</p>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight sm:text-5xl">
              100+ gold trading strategies, explained
            </h1>
            <p className="mt-4 text-base leading-relaxed text-[var(--fg-muted)] sm:text-lg">
              These are the strategy families used to trade gold (XAUUSD): trend following, breakouts, momentum, mean
              reversion, price action, sessions and key levels. Each page explains how the strategy works, when it
              suits gold and when to avoid it. Inside QuantForg, every strategy is tested on recent real gold data, so
              you can see which ones are working now.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link href="/register" className={pricingBtnPrimary}>Start free</Link>
              <Link href="/gold-trading-robot" className={pricingBtnSecondary}>How the gold robot works</Link>
            </div>
          </header>

          <nav aria-label="Strategy categories" className="mt-10 flex flex-wrap gap-2">
            {groups.map(([cat, list]) => (
              <a
                key={cat}
                href={`#${cat}`}
                className="rounded-full border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--fg-muted)] hover:border-[var(--accent)] hover:text-[var(--fg)]"
              >
                {categoryGuide(cat).label} ({list.length})
              </a>
            ))}
          </nav>

          {groups.map(([cat, list]) => {
            const g = categoryGuide(cat);
            return (
              <section key={cat} id={cat} className="mt-12 scroll-mt-24">
                <h2 className="text-2xl font-semibold tracking-tight">{g.label} strategies</h2>
                <p className="mt-2 max-w-3xl text-sm leading-relaxed text-[var(--fg-muted)]">{g.summary}</p>
                <ul className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {list.map((s) => (
                    <li key={s.slug}>
                      <Link
                        href={`/strategies/${s.slug}`}
                        className="block h-full rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] p-4 transition-colors hover:border-[var(--accent)]"
                      >
                        <span className="block text-sm font-semibold">{s.name}</span>
                        <span className="mt-1 block text-xs leading-relaxed text-[var(--fg-muted)]">{s.description}</span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </section>
            );
          })}

          <p className="mt-14 text-xs leading-relaxed text-[var(--fg-subtle)]">
            Educational content, not financial advice. Trading gold involves substantial risk of loss and past results do
            not guarantee future results. See our <Link href="/risk-disclosure" className="underline">risk disclosure</Link>.
          </p>
        </main>
        <PricingFooter />
      </div>
    </AuthFormProviders>
  );
}
