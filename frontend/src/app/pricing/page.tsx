import type { Metadata } from "next";
import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import {
  Activity,
  BarChart3,
  Blocks,
  BookOpen,
  Brain,
  Building2,
  Check,
  Crosshair,
  Gauge,
  GitBranch,
  Layers,
  LineChart,
  Radar,
  Scale,
  Shield,
  Sparkles,
  Target,
  TrendingUp,
  Workflow,
  X,
  Zap,
} from "lucide-react";
import { BrandLogo, BrandMark } from "@/components/brand/brand-logo";
import { FeatureTimeline } from "@/components/pricing/feature-timeline";
import { PricingFaq } from "@/components/pricing/pricing-faq";
import { ProductPreviews } from "@/components/pricing/product-previews";
import { RoiCalculator } from "@/components/pricing/roi-calculator";
import { StickyPurchaseBar } from "@/components/pricing/sticky-purchase-bar";
import {
  PricingFooter,
  PricingHeader,
  pricingBtnPrimary,
  pricingBtnSecondary,
} from "@/components/pricing/marketing-chrome";

export const metadata: Metadata = {
  title: "Pricing — QuantForg Institutional License",
  description:
    "Trade like an institution. One-time $2,499 lifetime license for QuantForg's complete AI trading ecosystem.",
};

const capabilities = [
  "Institutional AI",
  "24/7 Automation",
  "Professional Risk Engine",
  "Portfolio Intelligence",
  "Real-Time Execution",
  "Enterprise Architecture",
  "Future Updates Included",
];

const features: { title: string; icon: LucideIcon }[] = [
  { title: "Institutional AI Trading", icon: Brain },
  { title: "Smart Money Concepts", icon: Layers },
  { title: "Multi-Timeframe Analysis", icon: GitBranch },
  { title: "Order Blocks", icon: Blocks },
  { title: "Fair Value Gaps", icon: Crosshair },
  { title: "Liquidity Detection", icon: Radar },
  { title: "Dynamic Position Sizing", icon: Scale },
  { title: "Portfolio Risk Engine", icon: Gauge },
  { title: "AI Validation", icon: Sparkles },
  { title: "Automated Execution", icon: Zap },
  { title: "MT5 Live Trading", icon: Activity },
  { title: "Institutional Scalping", icon: Workflow },
  { title: "Winner Pyramiding", icon: LineChart },
  { title: "Break Even Automation", icon: Target },
  { title: "Dynamic Trailing Stops", icon: TrendingUp },
  { title: "Partial Take Profit", icon: Crosshair },
  { title: "Performance Analytics", icon: BarChart3 },
  { title: "Trade Journal", icon: BookOpen },
  { title: "Portfolio Dashboard", icon: Building2 },
  { title: "Lifetime Updates", icon: Sparkles },
  { title: "Professional Support", icon: Shield },
];

const trust = [
  "Lifetime Updates Included",
  "Professional Support",
  "Enterprise Architecture",
  "Institutional Design",
  "Secure Infrastructure",
  "One-Time Payment",
  "Premium Ownership",
];

const included = [
  "Everything Included",
  "No Hidden Fees",
  "One-Time Payment",
  "Lifetime Access",
  "Future Updates",
  "Professional Support",
];

export default function PricingPage() {
  return (
    <div className="min-h-screen overflow-x-clip pb-28">
      <PricingHeader active="pricing" />

      <main id="main-content" tabIndex={-1}>
        {/* 1. Cinematic hero */}
        <section className="qf-pricing-hero relative mx-auto w-full max-w-6xl overflow-hidden px-4 pb-12 pt-4 text-center sm:px-6 sm:pb-16 sm:pt-8">
          <div
            className="pointer-events-none absolute left-1/2 top-0 h-[28rem] w-[42rem] -translate-x-1/2 bg-[radial-gradient(ellipse_at_center,rgba(255,90,31,0.16),transparent_62%)]"
            aria-hidden
          />
          <div className="qf-fade-in relative">
            <div className="mx-auto mb-6 flex justify-center">
              <BrandLogo size={48} wordmark={false} priority />
            </div>
            <span className="qf-lifetime-badge" aria-label="Lifetime access">
              <span className="qf-lifetime-badge__glow" aria-hidden />
              LIFETIME ACCESS
            </span>
            <h1 className="mx-auto mt-6 max-w-4xl font-[family-name:var(--font-display)] text-[2.4rem] leading-[1.06] tracking-tight text-[var(--fg)] sm:text-5xl lg:text-[3.65rem]">
              Trade Like an{" "}
              <span className="text-[var(--accent)]">Institution.</span>
            </h1>
            <p className="mx-auto mt-5 max-w-2xl text-base text-[var(--fg-muted)] sm:text-lg">
              Own QuantForg forever with a single lifetime license and unlock the complete
              institutional AI trading ecosystem.
            </p>
            <p className="mx-auto mt-4 text-xs font-medium tracking-wide text-[var(--fg-subtle)] sm:text-sm">
              No subscriptions · No recurring fees · Lifetime ownership
            </p>
          </div>

          <div
            id="license"
            className="qf-fade-in qf-glass-card qf-glass-card--hero relative mx-auto mt-10 max-w-md overflow-hidden p-8 text-center sm:mt-12 sm:p-10 [animation-delay:90ms]"
          >
            <div
              className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(255,90,31,0.18),transparent_52%)]"
              aria-hidden
            />
            <div className="pointer-events-none absolute -right-4 top-6 opacity-[0.1]" aria-hidden>
              <BrandMark size={140} hiRes />
            </div>
            <div className="relative">
              <p className="qf-label text-[var(--accent)]">Institutional License</p>
              <div className="mx-auto my-4 h-px w-14 bg-[var(--accent)]/45" aria-hidden />
              <p className="font-[family-name:var(--font-display)] text-5xl font-semibold tracking-tight text-[var(--fg)] sm:text-6xl">
                $2,499
              </p>
              <p className="mt-3 text-sm font-semibold uppercase tracking-[0.14em] text-[var(--accent)]">
                Lifetime License
              </p>
              <p className="mt-1 text-sm text-[var(--fg-muted)]">One-Time Payment</p>
              <div className="mx-auto mt-4 h-px w-14 bg-[var(--accent)]/45" aria-hidden />
              <ul className="mt-5 space-y-2 text-left text-sm text-[var(--fg-muted)]">
                {included.map((line) => (
                  <li key={line} className="flex items-center gap-2">
                    <Check className="h-3.5 w-3.5 shrink-0 text-[var(--accent)]" strokeWidth={2.5} aria-hidden />
                    {line}
                  </li>
                ))}
              </ul>
              <Link
                href="/contact"
                className={`${pricingBtnPrimary} qf-btn-elevate mt-7 h-12 w-full text-base`}
              >
                Contact Support to Purchase
              </Link>
            </div>
          </div>
        </section>

        {/* 2. Social proof / capability highlights */}
        <section
          className="border-y border-[var(--border)] bg-[var(--bg-elevated)]/35 py-10 sm:py-12"
          aria-label="Product capability highlights"
        >
          <ul className="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-center gap-2.5 px-4 sm:gap-3 sm:px-6">
            {capabilities.map((c) => (
              <li
                key={c}
                className="rounded-full border border-[var(--border)] bg-[var(--surface)]/70 px-3.5 py-2 text-xs font-medium tracking-wide text-[var(--fg-muted)] sm:text-sm"
              >
                <span className="mr-1.5 text-[var(--accent)]" aria-hidden>
                  ◆
                </span>
                {c}
              </li>
            ))}
          </ul>
          <p className="mx-auto mt-4 max-w-xl px-4 text-center text-[11px] text-[var(--fg-subtle)]">
            Product capability highlights — not customer counts, revenue, or performance claims.
          </p>
        </section>

        {/* 3. Software previews */}
        <section
          className="mx-auto w-full max-w-6xl px-4 py-16 sm:px-6 sm:py-20"
          aria-labelledby="preview-heading"
        >
          <div className="mx-auto max-w-2xl text-center">
            <h2
              id="preview-heading"
              className="font-[family-name:var(--font-display)] text-2xl tracking-tight sm:text-3xl"
            >
              The QuantForg workspace
            </h2>
            <p className="mt-3 text-[var(--fg-muted)]">
              Premium product chrome — dashboards and desks rendered as institutional UI
              previews, not stock photography.
            </p>
          </div>
          <div className="mt-10">
            <ProductPreviews />
          </div>
        </section>

        {/* Feature grid */}
        <section
          className="mx-auto w-full max-w-6xl px-4 pb-16 sm:px-6 sm:pb-20"
          aria-labelledby="features-heading"
        >
          <div className="mx-auto max-w-2xl text-center">
            <h2
              id="features-heading"
              className="font-[family-name:var(--font-display)] text-2xl tracking-tight sm:text-3xl"
            >
              Everything included
            </h2>
            <p className="mt-3 text-[var(--fg-muted)]">One license. No tiers. No feature gates.</p>
          </div>
          <ul className="mt-10 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((f) => {
              const Icon = f.icon;
              return (
                <li
                  key={f.title}
                  className="qf-glass-card qf-glass-card--hover flex items-start gap-3 px-4 py-3.5"
                >
                  <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[var(--accent-soft)] text-[var(--accent)]">
                    <Icon className="h-4 w-4" strokeWidth={1.75} aria-hidden />
                  </span>
                  <span className="pt-1 text-sm font-medium leading-snug text-[var(--fg)]">
                    {f.title}
                  </span>
                </li>
              );
            })}
          </ul>
        </section>

        {/* 4. Feature timeline */}
        <section
          className="border-y border-[var(--border)] bg-[var(--bg-elevated)]/40 py-16 sm:py-20"
          aria-labelledby="flow-heading"
        >
          <div className="mx-auto w-full max-w-6xl px-4 sm:px-6">
            <div className="mx-auto mb-10 max-w-2xl text-center">
              <h2
                id="flow-heading"
                className="font-[family-name:var(--font-display)] text-2xl tracking-tight sm:text-3xl"
              >
                From analysis to performance
              </h2>
              <p className="mt-3 text-[var(--fg-muted)]">
                One continuous institutional loop — not a pile of disconnected tools.
              </p>
            </div>
            <FeatureTimeline />
          </div>
        </section>

        {/* 5. Value comparison */}
        <section
          className="mx-auto w-full max-w-6xl px-4 py-16 sm:px-6 sm:py-20"
          aria-labelledby="value-heading"
        >
          <div className="mx-auto max-w-2xl text-center">
            <h2
              id="value-heading"
              className="font-[family-name:var(--font-display)] text-2xl tracking-tight sm:text-3xl"
            >
              Institutional AI platform — without the annual stack
            </h2>
            <p className="mt-3 text-[var(--fg-muted)]">
              Typical fragmented tooling burns budget every year. QuantForg is paid once.
            </p>
          </div>
          <div className="mt-10 grid gap-4 md:grid-cols-2">
            <article className="qf-glass-card p-6 sm:p-8">
              <p className="qf-label">Institutional AI Platform</p>
              <p className="mt-2 text-sm text-[var(--fg-muted)]">Normally</p>
              <p className="mt-1 font-[family-name:var(--font-display)] text-4xl font-semibold tracking-tight text-[var(--danger)]">
                $8,500+
                <span className="text-lg font-medium text-[var(--fg-muted)]">/year</span>
              </p>
              <ul className="mt-6 space-y-2.5 text-sm text-[var(--fg-muted)]">
                {[
                  "Multiple subscriptions",
                  "Disconnected dashboards",
                  "Recurring monthly burn",
                  "Upgrade fees forever",
                ].map((x) => (
                  <li key={x} className="flex items-center gap-2">
                    <X className="h-4 w-4 text-[var(--danger)]" strokeWidth={2.25} aria-hidden />
                    {x}
                  </li>
                ))}
              </ul>
            </article>
            <article className="qf-glass-card relative overflow-hidden border-[var(--accent)]/30 p-6 sm:p-8">
              <div
                className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(255,90,31,0.14),transparent_55%)]"
                aria-hidden
              />
              <div className="relative">
                <BrandMark size={40} />
                <p className="qf-label mt-3 text-[var(--accent)]">QuantForg</p>
                <p className="mt-1 font-[family-name:var(--font-display)] text-4xl font-semibold tracking-tight sm:text-5xl">
                  $2,499
                </p>
                <p className="mt-2 text-sm font-medium text-[var(--fg)]">Pay Once</p>
                <p className="text-sm text-[var(--accent)]">Own Forever</p>
                <Link
                  href="/contact"
                  className={`${pricingBtnPrimary} qf-btn-elevate mt-6 h-11 w-full`}
                >
                  Contact Support to Purchase
                </Link>
              </div>
            </article>
          </div>
        </section>

        {/* 6. ROI */}
        <section className="mx-auto w-full max-w-6xl px-4 pb-16 sm:px-6 sm:pb-20" aria-labelledby="roi-heading">
          <h2 id="roi-heading" className="sr-only">
            ROI calculator
          </h2>
          <RoiCalculator />
        </section>

        {/* 7. Trust */}
        <section className="border-y border-[var(--border)] bg-[var(--bg-elevated)]/35 py-12" aria-label="Trust">
          <ul className="mx-auto flex max-w-6xl flex-wrap items-center justify-center gap-2.5 px-4 sm:gap-3 sm:px-6">
            {trust.map((t) => (
              <li
                key={t}
                className="inline-flex items-center gap-2 rounded-full border border-[var(--border)] bg-[var(--surface)]/80 px-3.5 py-2 text-xs text-[var(--fg-muted)] sm:text-sm"
              >
                <Check className="h-3.5 w-3.5 text-[var(--accent)]" strokeWidth={2.5} aria-hidden />
                {t}
              </li>
            ))}
          </ul>
        </section>

        {/* 9. Purchase card reprise */}
        <section className="mx-auto w-full max-w-6xl px-4 py-16 sm:px-6 sm:py-20" aria-labelledby="buy-heading">
          <div className="qf-glass-card qf-glass-card--hero relative mx-auto max-w-lg overflow-hidden p-8 text-center sm:p-10">
            <div
              className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(255,90,31,0.12),transparent_60%)]"
              aria-hidden
            />
            <div className="relative">
              <span className="qf-lifetime-badge">
                <span className="qf-lifetime-badge__glow" aria-hidden />
                LIFETIME ACCESS
              </span>
              <h2 id="buy-heading" className="mt-5 text-lg font-semibold tracking-tight">
                Institutional License
              </h2>
              <p className="mt-3 font-[family-name:var(--font-display)] text-5xl font-semibold tracking-tight">
                $2,499
              </p>
              <p className="mt-2 text-sm text-[var(--fg-muted)]">Lifetime Access · One-Time Payment</p>
              <p className="mt-4 text-sm font-medium text-[var(--fg)]">What&apos;s Included</p>
              <ul className="mx-auto mt-3 max-w-xs space-y-2 text-left text-sm text-[var(--fg-muted)]">
                {included.map((line) => (
                  <li key={line} className="flex items-center gap-2">
                    <Check className="h-3.5 w-3.5 text-[var(--accent)]" strokeWidth={2.5} aria-hidden />
                    {line}
                  </li>
                ))}
              </ul>
              <Link
                href="/contact"
                className={`${pricingBtnPrimary} qf-btn-elevate mt-8 h-12 w-full text-base`}
              >
                Contact Support to Purchase
              </Link>
              <Link href="/login" className={`${pricingBtnSecondary} mt-3 w-full`}>
                Already licensed? Sign in
              </Link>
            </div>
          </div>
        </section>

        {/* 8. FAQ */}
        <section className="mx-auto w-full max-w-6xl px-4 pb-20 sm:px-6 sm:pb-24" aria-labelledby="faq-heading">
          <div className="mx-auto mb-10 max-w-2xl text-center">
            <h2
              id="faq-heading"
              className="font-[family-name:var(--font-display)] text-2xl tracking-tight sm:text-3xl"
            >
              Frequently asked questions
            </h2>
            <p className="mt-3 text-[var(--fg-muted)]">Clear answers before you purchase.</p>
          </div>
          <PricingFaq />
        </section>
      </main>

      <PricingFooter />
      <StickyPurchaseBar />
    </div>
  );
}
