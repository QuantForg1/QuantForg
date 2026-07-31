import Link from "next/link";
import {
  Activity,
  BarChart3,
  Brain,
  ShieldCheck,
} from "lucide-react";
import { BrandLogo, BrandMark } from "@/components/brand/brand-logo";

const features = [
  {
    title: "Live portfolio sync",
    body: "Positions, equity, and exposure synchronized from your MT5 terminal — read-first, execution gated.",
    icon: Activity,
  },
  {
    title: "Risk before fill",
    body: "Pre-trade checks, SL/TP validation, and policy gates before any live order path is enabled.",
    icon: ShieldCheck,
  },
  {
    title: "Research loop",
    body: "Strategy evaluation, backtests, walk-forward, and paper trading in one workspace.",
    icon: BarChart3,
  },
  {
    title: "AI workspace",
    body: "Explain strategies, surface portfolio insights, and accelerate operator decisions.",
    icon: Brain,
  },
];

const stats = [
  { label: "Connectivity", value: "24/7" },
  { label: "Mock balances", value: "0" },
  { label: "Primary desks", value: "8" },
  { label: "Execution", value: "Gated" },
];

const btn =
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-[var(--radius-sm)] text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg)]";
const btnPrimary = `${btn} qf-btn-primary h-11 px-6`;
const btnSecondary = `${btn} h-11 px-6 border border-[var(--border-strong)] bg-transparent text-[var(--fg)] hover:bg-[var(--surface-2)]`;
const btnGhost = `${btn} h-10 px-4 text-[var(--fg-muted)] hover:bg-[var(--surface-2)] hover:text-[var(--fg)]`;
const btnOutline = `${btn} h-10 px-4 border border-[var(--border)] text-[var(--fg)] hover:border-[var(--border-strong)] hover:bg-[var(--surface-2)]`;

export default function LandingPage() {
  return (
    <div className="min-h-screen overflow-x-clip">
      <header className="mx-auto flex w-full max-w-6xl items-center justify-between gap-3 px-4 py-5 sm:px-6">
        <BrandLogo size={32} className="min-w-0" priority />
        <nav
          className="hidden items-center gap-6 text-sm text-[var(--fg-muted)] md:flex"
          aria-label="Marketing"
        >
          <a href="#features" className="hover:text-[var(--fg)]">
            Features
          </a>
          <a href="#platform" className="hover:text-[var(--fg)]">
            Platform
          </a>
          <Link href="/pricing" className="hover:text-[var(--fg)]">
            Pricing
          </Link>
        </nav>
        <div className="flex shrink-0 items-center gap-1.5 sm:gap-2" aria-label="Primary">
          <Link href="/login" className={`${btnGhost} max-sm:px-3`}>
            Sign In
          </Link>
          <Link href="/contact" className={`${btnOutline} max-sm:px-3`}>
            Contact Sales
          </Link>
        </div>
      </header>

      <main id="main-content" tabIndex={-1}>
        <section
          id="platform"
          className="relative mx-auto grid w-full max-w-6xl items-center gap-12 px-6 pb-16 pt-6 lg:grid-cols-[1.15fr_0.85fr] lg:min-h-[72vh]"
        >
          <div className="qf-fade-in">
            <h1 className="font-[family-name:var(--font-display)] text-[2.35rem] leading-[1.08] tracking-tight text-[var(--fg)] sm:text-5xl lg:text-[3.35rem]">
              The institutional trading terminal for operators who{" "}
              <span className="text-[var(--accent)]">demand clarity.</span>
            </h1>
            <p className="mt-5 max-w-xl text-base text-[var(--fg-muted)] sm:text-lg">
              Portfolio, risk, MT5 connectivity, research, and execution controls —
              designed like a product, measured like a desk.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/contact" className={btnPrimary}>
                Contact Support to Purchase
              </Link>
              <Link href="/login" className={btnSecondary}>
                Sign In
              </Link>
            </div>
          </div>

          <div className="qf-fade-in relative overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--surface)]/80 p-5 shadow-[var(--shadow-card)] [animation-delay:120ms]">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(0,212,224,0.16),transparent_48%)]" />
            <div className="relative space-y-5">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm text-[var(--fg-muted)]">Live book · MT5 gateway</p>
                <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--accent)]/30 bg-[var(--accent-soft)] px-2.5 py-1 text-[11px] font-medium tracking-wide text-[var(--accent)] uppercase">
                  <span className="qf-status-dot" data-state="ok" aria-hidden />
                  Live
                </span>
              </div>
              <div
                className="flex h-40 items-end gap-1.5"
                role="img"
                aria-label="Abstract terminal lattice — no sample trading figures"
              >
                {Array.from({ length: 20 }, (_, i) => (
                  <div
                    key={i}
                    className="flex-1 rounded-sm bg-[var(--accent)]/30"
                    style={{ height: `${30 + ((i * 41) % 58)}%` }}
                  />
                ))}
              </div>
              <ul className="space-y-2 text-sm text-[var(--fg-muted)]">
                <li>Positions and equity sync from your terminal</li>
                <li>Empty states when the gateway has no data</li>
                <li>No demo balances or placeholder trades</li>
              </ul>
            </div>
          </div>
        </section>

        <section
          id="features"
          className="mx-auto grid w-full max-w-6xl gap-4 px-6 pb-20 sm:grid-cols-2 lg:grid-cols-4"
          aria-label="Product capabilities"
        >
          {features.map((f) => {
            const Icon = f.icon;
            return (
              <div
                key={f.title}
                className="rounded-xl border border-[var(--border)] bg-[var(--surface)]/70 p-5 shadow-[var(--shadow-card)]"
              >
                <Icon
                  className="mb-3 h-5 w-5 text-[var(--accent)]"
                  strokeWidth={1.75}
                  aria-hidden
                />
                <h2 className="text-base font-semibold tracking-tight">{f.title}</h2>
                <p className="mt-2 text-sm text-[var(--fg-muted)]">{f.body}</p>
              </div>
            );
          })}
        </section>

        <section className="relative mx-auto mb-20 w-full max-w-6xl overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--surface)] px-6 py-12 sm:px-10">
          <div className="pointer-events-none absolute -right-8 top-1/2 hidden -translate-y-1/2 opacity-[0.12] md:block">
            <BrandMark size={280} hiRes />
          </div>
          <div className="relative max-w-2xl">
            <h2 className="font-[family-name:var(--font-display)] text-2xl tracking-tight sm:text-3xl">
              Built for operators.{" "}
              <span className="text-[var(--accent)]">Backed by clarity.</span>
            </h2>
            <p className="mt-3 text-[var(--fg-muted)]">
              Real connectivity, gated execution, and desks that stay honest when data is
              missing.
            </p>
          </div>
          <dl className="relative mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {stats.map((s) => (
              <div key={s.label}>
                <dt className="qf-caption uppercase tracking-[0.14em]">{s.label}</dt>
                <dd className="mt-1 font-[family-name:var(--font-display)] text-2xl font-semibold tracking-tight text-[var(--accent)]">
                  {s.value}
                </dd>
              </div>
            ))}
          </dl>
        </section>
      </main>

      <footer className="border-t border-[var(--border)] bg-[var(--bg-elevated)]/80">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-6 py-10 md:flex-row md:justify-between">
          <div className="max-w-xs space-y-3">
            <BrandLogo size={32} />
            <p className="text-sm text-[var(--fg-muted)]">
              Institutional trading operating system — licenses activated manually after payment
              verification.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-8 text-sm sm:grid-cols-3">
            <div>
              <p className="mb-3 font-medium text-[var(--fg)]">Product</p>
              <ul className="space-y-2 text-[var(--fg-muted)]">
                <li>
                  <a href="#features" className="hover:text-[var(--fg)]">
                    Features
                  </a>
                </li>
                <li>
                  <Link href="/pricing" className="hover:text-[var(--fg)]">
                    Pricing
                  </Link>
                </li>
                <li>
                  <a
                    href="mailto:support@quantforg.com?subject=QuantForg%20Documentation"
                    className="hover:text-[var(--fg)]"
                  >
                    Documentation
                  </a>
                </li>
              </ul>
            </div>
            <div>
              <p className="mb-3 font-medium text-[var(--fg)]">Sales</p>
              <ul className="space-y-2 text-[var(--fg-muted)]">
                <li>
                  <Link href="/contact" className="hover:text-[var(--fg)]">
                    Contact Sales
                  </Link>
                </li>
                <li>
                  <a href="mailto:support@quantforg.com" className="hover:text-[var(--fg)]">
                    Support
                  </a>
                </li>
                <li>
                  <Link href="/login" className="hover:text-[var(--fg)]">
                    Sign In
                  </Link>
                </li>
              </ul>
            </div>
            <div>
              <p className="mb-3 font-medium text-[var(--fg)]">Legal</p>
              <ul className="space-y-2 text-[var(--fg-muted)]">
                <li>
                  <a
                    href="mailto:support@quantforg.com?subject=Privacy%20Policy"
                    className="hover:text-[var(--fg)]"
                  >
                    Privacy
                  </a>
                </li>
                <li>
                  <a
                    href="mailto:support@quantforg.com?subject=Terms%20of%20Service"
                    className="hover:text-[var(--fg)]"
                  >
                    Terms
                  </a>
                </li>
              </ul>
            </div>
          </div>
        </div>
        <div className="border-t border-[var(--border)] px-6 py-4 text-center text-xs text-[var(--fg-subtle)]">
          © {new Date().getFullYear()} QuantForg. All rights reserved.
        </div>
      </footer>
    </div>
  );
}
