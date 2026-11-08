import Link from "next/link";
import type { ReactNode } from "react";
import { SiteFooter } from "@/components/marketing/site-footer";
import { SiteHeader } from "@/components/marketing/site-header";

export function LegalDoc({
  title,
  updated,
  children,
}: {
  title: string;
  updated: string;
  children: ReactNode;
}) {
  return (
    <div className="min-h-screen bg-[var(--bg)] text-[var(--fg)]">
      <SiteHeader />
      <main id="main-content" className="mx-auto max-w-3xl px-4 py-14 sm:px-6" tabIndex={-1}>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--accent)]">
          Legal
        </p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">{title}</h1>
        <p className="mt-2 text-sm text-[var(--fg-subtle)]">Last updated {updated}</p>
        <div className="prose-legal mt-10 space-y-5 text-sm leading-relaxed text-[var(--fg-muted)]">
          {children}
        </div>
        <p className="mt-10 text-sm text-[var(--fg-subtle)]">
          Questions?{" "}
          <Link href="/contact" className="text-[var(--accent)] hover:underline">
            Contact QuantForg
          </Link>{" "}
          or email{" "}
          <a href="mailto:support@quantforg.com" className="text-[var(--accent)] hover:underline">
            support@quantforg.com
          </a>
          .
        </p>
      </main>
      <SiteFooter />
    </div>
  );
}
