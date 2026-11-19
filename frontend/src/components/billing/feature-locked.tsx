"use client";

import Link from "next/link";
import { ArrowRight, Crown, Lock } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";

/**
 * Paid-feature lock screen. The blurred preview behind the card is purely
 * decorative placeholder art — no real signal data is ever rendered here
 * (the API refuses unpaid users with 402).
 */
export function FeatureLocked({
  title = "Signals Feature Locked",
  message = "Unlock high-probability trading signals and expert market insights by subscribing to a QuantForg plan.",
  subscribeHref = "/pricing",
  learnMoreHref = "/pricing#pricing-faq",
}: {
  title?: string;
  message?: string;
  subscribeHref?: string;
  learnMoreHref?: string;
}) {
  return (
    <section
      aria-labelledby="feature-locked-title"
      className="relative isolate overflow-hidden rounded-[28px] border border-[color-mix(in_srgb,var(--accent,#22d3ee)_28%,var(--border))] bg-[color-mix(in_srgb,#0b1f3a_72%,transparent)] shadow-[0_30px_80px_-30px_rgba(2,12,32,0.9)]"
    >
      <LockedPreview />

      <div className="relative z-10 flex min-h-[460px] flex-col items-center justify-center px-6 py-14 text-center">
        <div className="relative mb-7">
          <span
            aria-hidden
            className="absolute left-1/2 top-1/2 h-px w-[min(560px,80vw)] -translate-x-1/2 -translate-y-1/2 bg-[linear-gradient(90deg,transparent,rgba(56,189,248,0.85),transparent)]"
          />
          <span
            aria-hidden
            className="absolute inset-0 -m-6 rounded-full bg-sky-400/25 blur-2xl"
          />
          <ShieldLock />
        </div>

        <h2
          id="feature-locked-title"
          className="text-2xl font-bold tracking-tight text-white sm:text-[2rem]"
        >
          {title}
        </h2>
        <p className="mt-3 max-w-xl text-base leading-relaxed text-slate-200/90 sm:text-lg">
          {message}
        </p>

        <Link
          href={subscribeHref}
          className="mt-8 inline-flex items-center gap-3 rounded-full bg-[linear-gradient(180deg,#ff8a1f,#f25c05)] px-10 py-3.5 text-lg font-semibold text-white shadow-[0_12px_30px_-8px_rgba(242,92,5,0.75)] transition hover:brightness-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-300 focus-visible:ring-offset-2 focus-visible:ring-offset-[#0b1f3a]"
        >
          <Crown className="h-5 w-5" fill="currentColor" aria-hidden />
          Subscribe Now
        </Link>

        <Link
          href={learnMoreHref}
          className="mt-6 inline-flex items-center gap-2 text-sm font-medium text-sky-200 underline underline-offset-4 hover:text-white"
        >
          Learn more about subscription
          <ArrowRight className="h-4 w-4" aria-hidden />
        </Link>
      </div>
    </section>
  );
}

function ShieldLock() {
  return (
    <div className="relative h-32 w-28">
      <svg viewBox="0 0 112 128" className="h-full w-full drop-shadow-[0_0_24px_rgba(56,189,248,0.6)]" aria-hidden>
        <defs>
          <linearGradient id="qf-shield-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#1d64d8" />
            <stop offset="1" stopColor="#0b2f7a" />
          </linearGradient>
          <linearGradient id="qf-shield-edge" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#7dd3fc" />
            <stop offset="1" stopColor="#2563eb" />
          </linearGradient>
        </defs>
        <path
          d="M56 4 104 22v38c0 32-21 54-48 64C29 114 8 92 8 60V22L56 4Z"
          fill="url(#qf-shield-fill)"
          stroke="url(#qf-shield-edge)"
          strokeWidth="5"
          strokeLinejoin="round"
        />
      </svg>
      <Lock
        className="absolute left-1/2 top-[46%] h-12 w-12 -translate-x-1/2 -translate-y-1/2 text-white"
        strokeWidth={2.6}
        aria-hidden
      />
    </div>
  );
}

/** Decorative, blurred stand-in for the signal desk. Contains no real data. */
function LockedPreview() {
  const rows = [
    { w: "w-28", tone: "bg-emerald-400/60" },
    { w: "w-24", tone: "bg-emerald-400/60" },
    { w: "w-24", tone: "bg-rose-400/60" },
    { w: "w-28", tone: "bg-slate-300/50" },
    { w: "w-10", tone: "bg-slate-300/50" },
  ];
  return (
    <div
      aria-hidden
      className="pointer-events-none absolute inset-0 select-none blur-[7px] opacity-60"
    >
      <div className="grid h-full grid-cols-1 gap-8 p-10 md:grid-cols-[1fr_1.6fr]">
        <div className="flex flex-col items-center justify-center gap-4">
          <div className="h-20 w-20 rounded-full bg-sky-400/40" />
          <div className="h-3 w-24 rounded bg-slate-300/40" />
          <div className="text-5xl font-black tracking-wide text-slate-100/80">XAUUSD</div>
          <div className="h-3 w-28 rounded bg-slate-300/40" />
          <div className="mt-2 h-10 w-36 rounded-full bg-slate-500/30" />
        </div>
        <div className="hidden flex-col justify-center gap-7 rounded-2xl border border-white/10 bg-white/[0.03] p-8 md:flex">
          {rows.map((r, i) => (
            <div key={i} className="flex items-center justify-between">
              <div className="h-3 w-32 rounded bg-slate-300/30" />
              <div className={`h-3 ${r.w} rounded ${r.tone}`} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function SignalsLockedView() {
  return (
    <div className="qf-desk min-w-0 space-y-5">
      <PageHeader
        eyebrow="Research"
        title="Signals"
        description="High-probability trading signals from QuantForg's institutional intelligence."
      />
      <FeatureLocked />
    </div>
  );
}

