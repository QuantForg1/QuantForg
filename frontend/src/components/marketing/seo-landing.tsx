import Link from "next/link";
import type { ReactNode } from "react";
import { PricingFooter, PricingHeader, pricingBtnPrimary, pricingBtnSecondary } from "@/components/pricing/marketing-chrome";
import { AuthFormProviders } from "@/providers/auth-form-providers";
import { SITE_URL } from "@/lib/seo/strategy-content";

export type LandingSection = { title: string; body: ReactNode };
export type LandingFaq = { q: string; a: string };

export function SeoLanding({
  path,
  eyebrow,
  title,
  lead,
  highlights,
  sections,
  faq,
}: {
  path: string;
  eyebrow: string;
  title: string;
  lead: string;
  highlights: Array<{ title: string; text: string }>;
  sections: LandingSection[];
  faq: LandingFaq[];
}) {
  const jsonLd = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "WebPage",
        name: title,
        url: `${SITE_URL}${path}`,
        description: lead,
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
          { "@type": "ListItem", position: 2, name: eyebrow, item: `${SITE_URL}${path}` },
        ],
      },
    ],
  };
  return (
    <AuthFormProviders>
      <div className="relative min-h-screen bg-[var(--bg)] text-[var(--fg)]">
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
        <PricingHeader active="home" />
        <main id="main-content" tabIndex={-1} className="mx-auto max-w-5xl px-4 pb-16 pt-12 sm:px-6">
          <nav aria-label="Breadcrumb" className="text-xs text-[var(--fg-subtle)]">
            <Link href="/" className="hover:text-[var(--fg)]">Home</Link> / <span>{eyebrow}</span>
          </nav>
          <header className="mt-4 max-w-3xl">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--accent)]">{eyebrow}</p>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight sm:text-5xl">{title}</h1>
            <p className="mt-4 text-base leading-relaxed text-[var(--fg-muted)] sm:text-lg">{lead}</p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link href="/register" className={pricingBtnPrimary}>Start free</Link>
              <Link href="/pricing" className={pricingBtnSecondary}>See plans</Link>
            </div>
          </header>

          <ul className="mt-12 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {highlights.map((h) => (
              <li key={h.title} className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] p-5">
                <h2 className="text-sm font-semibold">{h.title}</h2>
                <p className="mt-2 text-sm leading-relaxed text-[var(--fg-muted)]">{h.text}</p>
              </li>
            ))}
          </ul>

          <div className="mt-12 max-w-3xl space-y-10">
            {sections.map((s) => (
              <section key={s.title}>
                <h2 className="text-2xl font-semibold tracking-tight">{s.title}</h2>
                <div className="mt-3 space-y-3 text-sm leading-relaxed text-[var(--fg-muted)] sm:text-base">{s.body}</div>
              </section>
            ))}
          </div>

          <section className="mt-14 max-w-3xl">
            <h2 className="text-2xl font-semibold tracking-tight">Frequently asked questions</h2>
            <dl className="mt-5 space-y-5">
              {faq.map((f) => (
                <div key={f.q}>
                  <dt className="text-sm font-semibold">{f.q}</dt>
                  <dd className="mt-1.5 text-sm leading-relaxed text-[var(--fg-muted)]">{f.a}</dd>
                </div>
              ))}
            </dl>
          </section>

          <section className="mt-14 rounded-[var(--radius-os)] border border-[var(--accent)]/35 bg-[var(--accent-soft)] p-6 text-center">
            <h2 className="text-xl font-semibold">Try QuantForg on your own MT5 account</h2>
            <p className="mx-auto mt-2 max-w-xl text-sm text-[var(--fg-muted)]">
              Create a free account, connect and verify your broker, and explore QuantForg AI. Subscribe when you are
              ready to switch the robot on.
            </p>
            <div className="mt-4 flex flex-wrap justify-center gap-3">
              <Link href="/register" className={pricingBtnPrimary}>Create free account</Link>
              <Link href="/strategies" className={pricingBtnSecondary}>Browse 100+ strategies</Link>
            </div>
          </section>

          <p className="mt-12 text-xs leading-relaxed text-[var(--fg-subtle)]">
            Trading gold involves substantial risk of loss. QuantForg is software; it does not guarantee profits and past
            results do not guarantee future results. See our <Link href="/risk-disclosure" className="underline">risk disclosure</Link>.
          </p>
        </main>
        <PricingFooter />
      </div>
    </AuthFormProviders>
  );
}
