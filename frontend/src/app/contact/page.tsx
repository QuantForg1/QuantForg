"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { BrandMark } from "@/components/brand/brand-logo";
import {
  PricingFooter,
  PricingHeader,
  pricingBtnPrimary,
  pricingBtnSecondary,
} from "@/components/pricing/marketing-chrome";
import { contactApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asRecord, str } from "@/lib/desk";

const EXPERIENCE = [
  "Beginner",
  "Intermediate",
  "Advanced",
  "Professional / Desk",
  "Institutional",
] as const;

const CONTACT_METHODS = ["Email", "Phone", "WhatsApp"] as const;

function ContactForm() {
  const router = useRouter();
  const params = useSearchParams();
  const planIntent = params.get("plan") || params.get("topic") || "";
  const [submitting, setSubmitting] = useState(false);
  const [accepted, setAccepted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  return (
    <div className="min-h-screen overflow-x-clip">
      <PricingHeader active="contact" />

      <main id="main-content" className="mx-auto w-full max-w-6xl px-4 pb-20 pt-6 sm:px-6" tabIndex={-1}>
        <div className="qf-fade-in mx-auto max-w-2xl text-center">
          <p className="qf-label text-[var(--accent)]">Sales & support</p>
          <h1 className="mt-3 font-[family-name:var(--font-display)] text-3xl tracking-tight sm:text-4xl">
            Contact QuantForg
          </h1>
          <p className="mt-3 text-[var(--fg-muted)]">
            Ask about Starter, Professional, or Premium subscription access. Paid entitlements are
            activated only after verified payment — never from a client-side click alone.
          </p>
        </div>

        <div className="mx-auto mt-10 grid max-w-5xl gap-5 lg:grid-cols-[1.15fr_0.85fr]">
          <section className="qf-glass-card p-6 sm:p-8" aria-labelledby="contact-form-heading">
            <h2 id="contact-form-heading" className="text-base font-semibold tracking-tight">
              Subscription request
            </h2>
            <p className="mt-1 text-sm text-[var(--fg-muted)]">
              Messages are stored securely for QuantForg follow-up. For self-serve payment, use{" "}
              <Link href="/billing/checkout" className="text-[var(--accent)] underline">
                crypto checkout
              </Link>
              .
            </p>

            <form
              className="mt-6 space-y-4"
              onSubmit={(e) => {
                e.preventDefault();
                if (!accepted || submitting) return;
                const form = e.currentTarget;
                const data = new FormData(form);
                setSubmitting(true);
                setError(null);
                void (async () => {
                  try {
                    const result = asRecord(
                      await contactApi.submitLead({
                        full_name: String(data.get("full_name") || ""),
                        email: String(data.get("email") || ""),
                        company: String(data.get("company") || ""),
                        country: String(data.get("country") || ""),
                        phone: String(data.get("phone") || ""),
                        experience: String(data.get("experience") || ""),
                        contact_method: String(data.get("contact_method") || ""),
                        subject: planIntent
                          ? `Plan interest: ${planIntent}`
                          : "Sales / support request",
                        message: [
                          String(data.get("message") || ""),
                          data.get("broker")
                            ? `Broker: ${String(data.get("broker"))}`
                            : "",
                        ]
                          .filter(Boolean)
                          .join("\n\n"),
                        plan_intent: planIntent,
                      }),
                    );
                    if (!result.stored) {
                      setError("Lead was not stored. Please try again.");
                      setSubmitting(false);
                      return;
                    }
                    router.push("/contact/success");
                  } catch (err) {
                    setError(
                      err instanceof ApiError
                        ? err.message || str(err.code, "Submit failed")
                        : "Submit failed",
                    );
                    setSubmitting(false);
                  }
                })();
              }}
            >
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Full Name" id="full_name" required>
                  <input
                    id="full_name"
                    name="full_name"
                    required
                    autoComplete="name"
                    className="qf-contact-input"
                  />
                </Field>
                <Field label="Company (optional)" id="company">
                  <input
                    id="company"
                    name="company"
                    autoComplete="organization"
                    className="qf-contact-input"
                  />
                </Field>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Country" id="country" required>
                  <input
                    id="country"
                    name="country"
                    required
                    autoComplete="country-name"
                    className="qf-contact-input"
                  />
                </Field>
                <Field label="Email" id="email" required>
                  <input
                    id="email"
                    name="email"
                    type="email"
                    required
                    autoComplete="email"
                    className="qf-contact-input"
                  />
                </Field>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Phone / WhatsApp" id="phone" required>
                  <input
                    id="phone"
                    name="phone"
                    type="tel"
                    required
                    autoComplete="tel"
                    className="qf-contact-input"
                  />
                </Field>
                <Field label="Trading Experience" id="experience" required>
                  <select id="experience" name="experience" required className="qf-contact-input">
                    <option value="">Select…</option>
                    {EXPERIENCE.map((x) => (
                      <option key={x} value={x}>
                        {x}
                      </option>
                    ))}
                  </select>
                </Field>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Broker (optional)" id="broker">
                  <input id="broker" name="broker" className="qf-contact-input" />
                </Field>
                <Field label="Preferred Contact Method" id="contact_method" required>
                  <select
                    id="contact_method"
                    name="contact_method"
                    required
                    className="qf-contact-input"
                  >
                    <option value="">Select…</option>
                    {CONTACT_METHODS.map((m) => (
                      <option key={m} value={m}>
                        {m}
                      </option>
                    ))}
                  </select>
                </Field>
              </div>

              <Field label="Message" id="message" required>
                <textarea
                  id="message"
                  name="message"
                  required
                  rows={5}
                  className="qf-contact-input min-h-[7.5rem] resize-y"
                  placeholder="Tell us about your desk, volume, and timeline…"
                />
              </Field>

              <label className="flex items-start gap-3 rounded-xl border border-[var(--border)] bg-[var(--bg-elevated)]/50 px-4 py-3 text-sm text-[var(--fg-muted)]">
                <input
                  type="checkbox"
                  className="mt-0.5 h-4 w-4 shrink-0 accent-[var(--accent)]"
                  checked={accepted}
                  onChange={(e) => setAccepted(e.target.checked)}
                  required
                />
                <span>
                  I understand paid access is activated only after verified payment and server-side
                  license provisioning — not from this form alone.
                </span>
              </label>

              {error ? (
                <p className="rounded-lg border border-[var(--danger)]/40 bg-[var(--danger-soft)] px-3 py-2 text-sm text-[var(--danger)]">
                  {error}
                </p>
              ) : null}

              <button
                type="submit"
                disabled={submitting || !accepted}
                className={`${pricingBtnPrimary} qf-btn-elevate h-12 w-full text-base disabled:opacity-50`}
              >
                {submitting ? "Submitting…" : "Submit request"}
              </button>
            </form>
          </section>

          <aside className="qf-glass-card h-fit border-[var(--accent)]/20 p-6 sm:p-8">
            <BrandMark size={40} />
            <p className="qf-label mt-4 text-[var(--accent)]">Subscription plans</p>
            <p className="mt-2 font-[family-name:var(--font-display)] text-4xl font-semibold tracking-tight">
              From $49
            </p>
            <p className="mt-1 text-sm text-[var(--fg-muted)]">
              Starter · Professional · Premium · monthly
            </p>
            <ul className="mt-6 space-y-2.5 text-sm text-[var(--fg-muted)]">
              {[
                "NOWPayments LIVE crypto checkout available when signed in",
                "Verified payment required for paid access",
                "Software access — not profit guarantees",
                "Risk disclosure applies to all trading",
              ].map((line) => (
                <li key={line} className="flex gap-2">
                  <span className="text-[var(--accent)]" aria-hidden>
                    ✓
                  </span>
                  {line}
                </li>
              ))}
            </ul>
            <p className="mt-6 text-xs leading-relaxed text-[var(--fg-subtle)]">
              Prefer email?{" "}
              <a href="mailto:support@quantforg.com" className="text-[var(--accent)]">
                support@quantforg.com
              </a>
            </p>
            <Link href="/pricing" className={`${pricingBtnSecondary} mt-6 w-full`}>
              Back to pricing
            </Link>
          </aside>
        </div>
      </main>

      <PricingFooter />
    </div>
  );
}

export default function ContactPurchasePage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[var(--bg)]" />}>
      <ContactForm />
    </Suspense>
  );
}

function Field({
  label,
  id,
  required,
  children,
}: {
  label: string;
  id: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-sm font-medium text-[var(--fg)]">
        {label}
        {required ? <span className="text-[var(--accent)]"> *</span> : null}
      </label>
      {children}
    </div>
  );
}
