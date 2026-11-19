import Link from "next/link";
import { SiteFooter } from "@/components/marketing/site-footer";
import { SiteHeader } from "@/components/marketing/site-header";
import {
  LEARN_PAGES,
  LEARN_UPDATED,
  learnPath,
  type LearnPage,
} from "@/lib/marketing/learn-catalog";

const SITE =
  process.env.NEXT_PUBLIC_APP_URL?.replace(/\/$/, "") || "https://www.quantforg.com";

export function LearnArticle({ page }: { page: LearnPage }) {
  const faq = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: page.faqs.map((item) => ({
      "@type": "Question",
      name: item.question,
      acceptedAnswer: { "@type": "Answer", text: item.answer },
    })),
  };
  const article = {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: page.title,
    description: page.description,
    dateModified: "2026-11-19",
    author: { "@type": "Organization", name: "QuantForg", url: SITE },
    publisher: { "@type": "Organization", name: "QuantForg", url: SITE },
    mainEntityOfPage: `${SITE}${learnPath(page.slug)}`,
  };

  return (
    <div className="min-h-screen overflow-x-hidden bg-[var(--bg)] text-[var(--fg)]">
      <SiteHeader active="learn" />
      <main id="main-content" className="mx-auto max-w-3xl px-4 py-12 sm:px-6 sm:py-14" tabIndex={-1}>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--accent)]">
          Product guide
        </p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">{page.title}</h1>
        <p className="mt-3 text-base leading-relaxed text-[var(--fg-muted)]">{page.description}</p>
        <p className="mt-2 text-sm text-[var(--fg-subtle)]">Updated {LEARN_UPDATED}</p>

        <nav className="mt-6 flex flex-wrap gap-2 border-b border-[var(--border)] pb-4" aria-label="Product guides">
          <Link
            href="/learn"
            className="rounded-[var(--radius-sm)] border border-[var(--border)] px-3 py-1.5 text-sm text-[var(--fg-muted)] hover:text-[var(--fg)]"
          >
            All guides
          </Link>
          {LEARN_PAGES.map((item) => {
            const active = item.slug === page.slug;
            return (
              <Link
                key={item.slug}
                href={learnPath(item.slug)}
                aria-current={active ? "page" : undefined}
                className={
                  active
                    ? "rounded-[var(--radius-sm)] border border-[var(--accent)]/40 bg-[var(--accent-soft)] px-3 py-1.5 text-sm font-medium text-[var(--fg)]"
                    : "rounded-[var(--radius-sm)] border border-[var(--border)] px-3 py-1.5 text-sm text-[var(--fg-muted)] hover:text-[var(--fg)]"
                }
              >
                {item.title}
              </Link>
            );
          })}
        </nav>

        <div className="mt-8 space-y-8">
          {page.sections.map((section) => (
            <section key={section.heading}>
              <h2 className="text-lg font-semibold text-[var(--fg)]">{section.heading}</h2>
              {section.paragraphs.map((paragraph) => (
                <p key={paragraph} className="mt-3 text-sm leading-relaxed text-[var(--fg-muted)] sm:text-base">
                  {paragraph}
                </p>
              ))}
            </section>
          ))}
        </div>

        <section className="mt-10" aria-labelledby="learn-faq">
          <h2 id="learn-faq" className="text-lg font-semibold text-[var(--fg)]">
            Questions
          </h2>
          <dl className="mt-4 space-y-4">
            {page.faqs.map((item) => (
              <div key={item.question} className="rounded-[var(--radius-os)] border border-[var(--border)] p-4">
                <dt className="font-medium text-[var(--fg)]">{item.question}</dt>
                <dd className="mt-2 text-sm leading-relaxed text-[var(--fg-muted)]">{item.answer}</dd>
              </div>
            ))}
          </dl>
        </section>

        <p className="mt-10 text-sm leading-relaxed text-[var(--fg-subtle)]">
          Software access is not a promise of trading profits. Read the{" "}
          <Link href="/risk-disclosure" className="text-[var(--accent)] hover:underline">
            risk disclosure
          </Link>
          , the{" "}
          <Link href="/pricing" className="text-[var(--accent)] hover:underline">
            plans
          </Link>
          , and{" "}
          <Link href="/contact" className="text-[var(--accent)] hover:underline">
            contact
          </Link>{" "}
          if you need a person.
        </p>
      </main>
      <SiteFooter />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(article) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(faq) }} />
    </div>
  );
}
