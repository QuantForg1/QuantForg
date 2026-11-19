import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { PricingFooter, PricingHeader, pricingBtnPrimary, pricingBtnSecondary } from "@/components/pricing/marketing-chrome";
import { AuthFormProviders } from "@/providers/auth-form-providers";
import {
  SITE_URL,
  STRATEGIES,
  categoryGuide,
  relatedStrategies,
  strategyBySlug,
  strategyFaq,
} from "@/lib/seo/strategy-content";

type Params = { params: Promise<{ slug: string }> };

export const dynamicParams = false;

export function generateStaticParams() {
  return STRATEGIES.map((s) => ({ slug: s.slug }));
}

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { slug } = await params;
  const s = strategyBySlug(slug);
  if (!s) return {};
  const g = categoryGuide(s.category);
  const title = `${s.name} Strategy for Gold (XAUUSD): How It Works`;
  const description = `${s.description} Learn how the ${s.name} ${g.label.toLowerCase()} strategy works on gold, when it performs best, when to avoid it and how to automate it on MT5.`;
  return {
    title: { absolute: `${title} · QuantForg` },
    description: description.slice(0, 300),
    alternates: { canonical: `/strategies/${s.slug}` },
    openGraph: {
      type: "article",
      title,
      description: s.description,
      url: `/strategies/${s.slug}`,
      images: [{ url: "/og-image.png", width: 1200, height: 630, alt: `${s.name} gold strategy` }],
    },
  };
}

function Bullets({ items }: { items: string[] }) {
  return (
    <ul className="mt-3 space-y-2">
      {items.map((x) => (
        <li key={x} className="flex gap-2 text-sm leading-relaxed text-[var(--fg-muted)]">
          <span aria-hidden className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--accent)]" />
          {x}
        </li>
      ))}
    </ul>
  );
}

export default async function StrategyPage({ params }: Params) {
  const { slug } = await params;
  const s = strategyBySlug(slug);
  if (!s) notFound();
  const g = categoryGuide(s.category);
  const faq = strategyFaq(s);
  const related = relatedStrategies(s);
  const url = `${SITE_URL}/strategies/${s.slug}`;
  const jsonLd = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "Article",
        headline: `${s.name} strategy for gold (XAUUSD)`,
        description: s.description,
        url,
        mainEntityOfPage: url,
        about: ["Gold trading", "XAUUSD", g.label],
        author: { "@type": "Organization", name: "QuantForg", url: SITE_URL },
        publisher: {
          "@type": "Organization",
          name: "QuantForg",
          logo: { "@type": "ImageObject", url: `${SITE_URL}/brand/quantforg-mark.png` },
        },
        image: `${SITE_URL}/og-image.png`,
      },
      {
        "@type": "FAQPage",
        mainEntity: faq.map((f) => ({
          "@type": "Question",
          name: f.q,
          acceptedAnswer: { "@type": "Answer", text: f.a },
        })),
      },
      {
        "@type": "BreadcrumbList",
        itemListElement: [
          { "@type": "ListItem", position: 1, name: "Home", item: SITE_URL },
          { "@type": "ListItem", position: 2, name: "Strategies", item: `${SITE_URL}/strategies` },
          { "@type": "ListItem", position: 3, name: s.name, item: url },
        ],
      },
    ],
  };

  return (
    <AuthFormProviders>
      <div className="relative min-h-screen bg-[var(--bg)] text-[var(--fg)]">
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
        <PricingHeader active="home" />
        <main id="main-content" tabIndex={-1} className="mx-auto max-w-3xl px-4 pb-16 pt-12 sm:px-6">
          <nav aria-label="Breadcrumb" className="text-xs text-[var(--fg-subtle)]">
            <Link href="/" className="hover:text-[var(--fg)]">Home</Link> /{" "}
            <Link href="/strategies" className="hover:text-[var(--fg)]">Strategies</Link> / <span>{s.name}</span>
          </nav>
          <article>
            <header className="mt-4">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--accent)]">
                {g.label} strategy · Gold (XAUUSD)
              </p>
              <h1 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">{s.name} strategy for gold</h1>
              <p className="mt-4 text-lg leading-relaxed text-[var(--fg-muted)]">{s.description}</p>
            </header>

            <section className="mt-10">
              <h2 className="text-xl font-semibold">How {s.name} works on gold</h2>
              <p className="mt-3 text-sm leading-relaxed text-[var(--fg-muted)]">{g.howItWorksOnGold}</p>
              <p className="mt-3 text-sm leading-relaxed text-[var(--fg-muted)]">
                The {s.name} rule is fully objective: given the same candles, it always produces the same signal. A
                signal only fires on the candle where its condition becomes true, so it can be tested fairly on
                historical data and run automatically on MetaTrader 5.
              </p>
            </section>

            <section className="mt-8 grid gap-6 sm:grid-cols-2">
              <div>
                <h2 className="text-lg font-semibold">When it works best</h2>
                <Bullets items={g.bestConditions} />
              </div>
              <div>
                <h2 className="text-lg font-semibold">When to avoid it</h2>
                <Bullets items={g.avoidWhen} />
              </div>
            </section>

            <section className="mt-8">
              <h2 className="text-xl font-semibold">Risk management for {s.name}</h2>
              <p className="mt-3 text-sm leading-relaxed text-[var(--fg-muted)]">
                Gold can move several dollars in minutes, so the stop is sized from volatility (ATR), not a fixed
                number of pips. A common, testable plan is a stop of 1.5×ATR(14) and a target of at least 1.5 times the
                risk. Risk only a small, fixed share of the account per trade, and never average down into a losing
                position.
              </p>
              <h3 className="mt-5 text-base font-semibold">Common mistakes</h3>
              <Bullets items={g.commonMistakes} />
            </section>

            <section className="mt-10 rounded-[var(--radius-os)] border border-[var(--accent)]/35 bg-[var(--accent-soft)] p-5">
              <h2 className="text-lg font-semibold">See how {s.name} is performing on gold right now</h2>
              <p className="mt-2 text-sm leading-relaxed text-[var(--fg-muted)]">
                QuantForg replays {s.name} and {STRATEGIES.length - 1} other strategies on recent real XAUUSD data, with
                spread included, and ranks them by results. Ask QuantForg AI to explain any strategy against the live
                market, or let the gold robot trade for you on your own MT5 account with risk limits on every trade.
              </p>
              <div className="mt-4 flex flex-wrap gap-3">
                <Link href="/register" className={pricingBtnPrimary}>Start free</Link>
                <Link href="/pricing" className={pricingBtnSecondary}>See plans</Link>
              </div>
            </section>

            <section className="mt-10">
              <h2 className="text-xl font-semibold">Frequently asked questions</h2>
              <dl className="mt-4 space-y-5">
                {faq.map((f) => (
                  <div key={f.q}>
                    <dt className="text-sm font-semibold">{f.q}</dt>
                    <dd className="mt-1.5 text-sm leading-relaxed text-[var(--fg-muted)]">{f.a}</dd>
                  </div>
                ))}
              </dl>
            </section>
          </article>

          {related.length ? (
            <aside className="mt-12">
              <h2 className="text-lg font-semibold">Related {g.label.toLowerCase()} strategies</h2>
              <ul className="mt-3 grid gap-2 sm:grid-cols-2">
                {related.map((r) => (
                  <li key={r.slug}>
                    <Link
                      href={`/strategies/${r.slug}`}
                      className="block rounded-[var(--radius-sm)] border border-[var(--border)] px-3 py-2.5 text-sm hover:border-[var(--accent)]"
                    >
                      {r.name}
                    </Link>
                  </li>
                ))}
              </ul>
              <Link href="/strategies" className="mt-4 inline-block text-sm text-[var(--accent)] hover:underline">
                All 100+ gold strategies →
              </Link>
            </aside>
          ) : null}

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
