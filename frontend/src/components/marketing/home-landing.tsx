import Link from "next/link";
import {
  ArrowRight,
  Brain,
  Cable,
  Check,
  ChevronRight,
  CircleDollarSign,
  Clock,
  Lock,
  Play,
  Shield,
  ShieldCheck,
  Sparkles,
  Workflow,
} from "lucide-react";
import { SiteFooter } from "@/components/marketing/site-footer";
import { SiteHeader } from "@/components/marketing/site-header";
import { FaqList } from "@/components/marketing/faq-list";
import { MountainBackdrop } from "@/components/brand/mountain-backdrop";
import { WeltradeLogo } from "@/components/brand/weltrade-logo";
import {
  OWNER_MAX_LOT,
  OWNER_MAX_PLANNED_RISK_PCT,
  OWNER_MAX_SPREAD,
} from "@/lib/execution/ticket-risk";

const btn =
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-[var(--radius-sm)] text-sm font-semibold transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg)]";

const CAPABILITIES = [
  {
    title: "MT5 Connectivity",
    body: "Secure connection to the MetaTrader 5 account you authorize.",
    icon: Cable,
  },
  {
    title: "AI Market Intelligence",
    body: "Research scoring on the gold desk. A score is not an executed trade.",
    icon: Brain,
  },
  {
    title: "Automated Risk Management",
    body: "Existing risk checks run before an order is handed to the broker.",
    icon: Shield,
  },
  {
    title: "24/5 Trading",
    body: "The gold session runs Monday to Friday. Weekend hours are not treated as an active session.",
    icon: Clock,
  },
] as const;

const ROBOT = [
  { title: "Market Scanning", body: "Reads the gold feed from the connected gateway." },
  { title: "AI Analysis", body: "Scores structure, momentum, and context." },
  { title: "Strategy Engine", body: "Evaluates modules already in the product." },
  { title: "Risk Validation", body: "Blocks orders that fail planned risk or spread limits." },
  { title: "Order Execution", body: "Sends approved orders through OMS and MT5." },
  { title: "Trade Management", body: "Monitors open positions and protective stops." },
  { title: "Trade Closure", body: "Closes or updates only through the broker connection." },
  { title: "Performance", body: "History is the broker’s deals — never invented." },
] as const;

const STRATEGIES = [
  "Trend Following",
  "Liquidity Sweep",
  "Breakout",
  "Mean Reversion",
  "Momentum",
  "Order Block",
  "Fair Value Gap",
  "RSI / MACD",
  "Bollinger Bands",
] as const;

const RISK_CONTROLS = [
  ["Risk per Trade", `${OWNER_MAX_PLANNED_RISK_PCT}%`],
  ["Aggregate Open Risk", "30%"],
  ["Max Lot", String(OWNER_MAX_LOT)],
  ["Max Spread", `${OWNER_MAX_SPREAD.toFixed(2)} USD`],
  ["Daily Loss Protection", "48%"],
  ["ATR Stop Multiplier", "1.00"],
  ["Max Positions", "5"],
  ["Symbol Allowlist", "XAUUSD (Gold)"],
] as const;

const SECURITY = [
  {
    title: "Encrypted credentials",
    body: "Passwords are entered to sign in or connect. They are not printed back on the screen.",
    icon: Lock,
  },
  {
    title: "Secure connection",
    body: "The existing MT5 gateway talks to the server on the account you connect.",
    icon: Cable,
  },
  {
    title: "Account-level permissions",
    body: "Trading uses the rights on that broker login. A missing permission stops the action.",
    icon: ShieldCheck,
  },
  {
    title: "Independent risk controls",
    body: "The risk engine can refuse an order before it reaches the broker.",
    icon: Shield,
  },
] as const;

const MT5_BROKERS = [
  "MetaTrader 5",
  "IC Markets",
  "Exness",
  "Pepperstone",
  "XM",
  "FP Markets",
  "Eightcap",
] as const;

function SectionTitle({
  id,
  kicker,
  title,
  body,
}: {
  id?: string;
  kicker: string;
  title: string;
  body: string;
}) {
  return (
    <div className="mb-8 max-w-3xl">
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--accent)]">
        {kicker}
      </p>
      <h2
        id={id}
        className="mt-2 text-2xl font-semibold tracking-tight text-[var(--fg)] sm:text-3xl"
      >
        {title}
      </h2>
      <p className="mt-3 text-sm leading-relaxed text-[var(--fg-muted)] sm:text-base">
        {body}
      </p>
    </div>
  );
}

function TerminalPreview() {
  return (
    <div className="relative mx-auto w-full max-w-xl">
      <div
        className="absolute -inset-x-6 -bottom-8 top-10 rounded-[2rem] bg-[radial-gradient(ellipse_at_center,rgba(0,212,224,0.18),transparent_65%)]"
        aria-hidden
      />
      <div className="relative rounded-[1.6rem] border border-[color-mix(in_srgb,var(--brand-electric)_35%,var(--border))] bg-gradient-to-b from-[var(--surface)] to-[var(--brand-navy)] p-3 shadow-[0_30px_80px_rgba(2,12,28,0.55)]">
        <div className="rounded-[1.25rem] border border-[var(--border-strong)] bg-[var(--bg-elevated)] p-2.5">
          <div className="mb-2 flex items-center gap-1.5 px-1">
            <span className="h-2.5 w-2.5 rounded-full bg-[#ff5f57]" />
            <span className="h-2.5 w-2.5 rounded-full bg-[#febc2e]" />
            <span className="h-2.5 w-2.5 rounded-full bg-[#28c840]" />
            <span className="ml-2 text-[10px] text-[var(--fg-subtle)]">
              Live Trading Terminal
            </span>
          </div>
          <div className="grid grid-cols-[4.5rem_1fr] overflow-hidden rounded-[1rem] border border-[var(--border)] bg-[var(--bg-elevated)]">
            <aside className="space-y-2 border-r border-[var(--border)] bg-[var(--surface)]/80 p-2 text-[9px] text-[var(--fg-subtle)]">
              {[
                "Dashboard",
                "Positions",
                "Strategies",
                "Analysis",
                "Risk",
                "Broker",
                "History",
                "Settings",
              ].map((item, i) => (
                <p
                  key={item}
                  className={
                    i === 0
                      ? "rounded-md bg-[var(--accent-soft)] px-1.5 py-1 font-medium text-[var(--accent)]"
                      : "px-1.5 py-1"
                  }
                >
                  {item}
                </p>
              ))}
            </aside>
            <div className="space-y-2 p-3">
              <div className="flex items-center justify-between gap-2">
                <p className="text-xs font-semibold">XAUUSD (Gold)</p>
                <span className="inline-flex items-center gap-1 rounded-full border border-[var(--success)]/35 bg-[var(--success-soft)] px-2 py-0.5 text-[10px] text-[var(--success)]">
                  <span className="h-1.5 w-1.5 rounded-full bg-[var(--success)]" />
                  Live
                </span>
              </div>
              <div
                className="flex h-28 items-end gap-1 rounded-lg border border-[var(--border)] bg-[var(--bg)]/50 px-2 py-2"
                role="img"
                aria-label="Decorative chart frame, not a price history"
              >
                {Array.from({ length: 22 }, (_, i) => {
                  const up = i % 3 !== 0;
                  const body = 16 + ((i * 13) % 48);
                  return (
                    <span
                      key={i}
                      className="flex flex-1 flex-col items-center justify-end"
                      style={{ height: "100%" }}
                    >
                      <span
                        className={
                          up
                            ? "w-1.5 rounded-sm bg-[var(--success)]/75"
                            : "w-1.5 rounded-sm bg-[var(--danger)]/75"
                        }
                        style={{ height: body }}
                      />
                    </span>
                  );
                })}
              </div>
              <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)]/70 p-2">
                <p className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                  AI Market Bias
                </p>
                <p className="mt-1 text-sm font-semibold text-[var(--fg)]">
                  Appears after connection
                </p>
                <p className="mt-1 text-[10px] text-[var(--fg-muted)]">
                  Trend · Momentum · Volatility · Confidence stay empty until live research
                  arrives.
                </p>
              </div>
              <dl className="grid grid-cols-2 gap-1.5 text-[10px] sm:grid-cols-4">
                {[
                  ["Account Equity", "—"],
                  ["Open Positions", "—"],
                  ["Today’s P&L", "—"],
                  ["Win Rate", "—"],
                ].map(([label, value]) => (
                  <div
                    key={label}
                    className="rounded-md border border-[var(--border)] bg-[var(--bg)]/40 px-2 py-1.5"
                  >
                    <dt className="text-[var(--fg-subtle)]">{label}</dt>
                    <dd className="mt-0.5 font-medium text-[var(--fg)]">{value}</dd>
                  </div>
                ))}
              </dl>
            </div>
          </div>
        </div>
        <div className="mx-auto mt-2 h-1.5 w-16 rounded-full bg-[var(--surface-3)]" aria-hidden />
      </div>
    </div>
  );
}

export function HomeLanding() {
  return (
    <div className="min-h-screen overflow-x-clip text-[var(--fg)]">
      <SiteHeader active="home" />
      <main id="main-content" tabIndex={-1}>
        <section id="platform" className="relative overflow-hidden">
          <MountainBackdrop withCandles intensity="vivid" />
          <div className="relative mx-auto grid w-full max-w-6xl items-center gap-10 px-4 py-14 sm:px-6 lg:grid-cols-[1.05fr_0.95fr] lg:py-20">
            <div>
              <p className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-muted)] backdrop-blur-md">
                <Sparkles className="h-3.5 w-3.5 text-[var(--cta)]" aria-hidden />
                Institutional AI Trading · MT5 · 24/5 gold session
              </p>
              <h1 className="mt-5 font-[family-name:var(--font-display)] text-4xl leading-[1.05] tracking-tight sm:text-5xl lg:text-6xl">
                Your Trading.
                <span className="mt-1 block">Our Intelligence.</span>
                <span className="mt-1 block text-[var(--accent)]">Fully Connected.</span>
              </h1>
              <p className="mt-5 max-w-xl text-base leading-relaxed text-[var(--fg-muted)] sm:text-lg">
                QuantForg is an Institutional AI Trading Platform that connects traders to their
                broker accounts and provides market intelligence, strategy evaluation, risk
                management, and automated execution under approved settings. Software access is
                not a promise of profits.
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <Link href="/register" className={`${btn} qf-btn-cta h-12 px-5`}>
                  Connect Your Broker
                  <ArrowRight className="h-4 w-4" aria-hidden />
                </Link>
                <Link
                  href="/#how-it-works"
                  className={`${btn} qf-glass-card h-12 border-0 px-5 text-[var(--fg)] hover:bg-[color-mix(in_srgb,var(--surface-2)_72%,transparent)]`}
                >
                  <Play className="h-4 w-4" aria-hidden />
                  Explore How It Works
                </Link>
              </div>
              <ul className="mt-6 flex flex-col gap-2 text-sm text-[var(--fg-muted)] sm:flex-row sm:flex-wrap sm:gap-x-5">
                {[
                  "Works with your MT5 broker",
                  "Your capital, your control",
                  "Risk checks before every order",
                ].map((item) => (
                  <li key={item} className="inline-flex items-center gap-2">
                    <Check className="h-4 w-4 text-[var(--success)]" aria-hidden />
                    {item}
                  </li>
                ))}
              </ul>
            </div>
            <TerminalPreview />
          </div>
        </section>

        <section
          id="features"
          className="mx-auto grid w-full max-w-6xl gap-3 px-4 py-8 sm:grid-cols-2 sm:px-6 lg:grid-cols-4"
          aria-label="Platform capabilities"
        >
          {CAPABILITIES.map((item) => {
            const Icon = item.icon;
            return (
              <article
                key={item.title}
                className="qf-glass-card qf-glass-card--hover p-4"
              >
                <span className="mb-3 inline-flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--accent-soft)] text-[var(--accent)]">
                  <Icon className="h-5 w-5" aria-hidden />
                </span>
                <h2 className="text-base font-semibold">{item.title}</h2>
                <p className="mt-1 text-sm text-[var(--fg-muted)]">{item.body}</p>
              </article>
            );
          })}
        </section>

        <section id="how-it-works" className="mx-auto w-full max-w-6xl px-4 py-12 sm:px-6">
          <SectionTitle
            kicker="Get started"
            title="How to Connect Your Broker — 3 Simple Steps"
            body="You connect the account you already have. QuantForg does not open a broker account for you."
          />
          <ol className="grid gap-4 lg:grid-cols-3">
            <li className="qf-glass-card qf-glass-card--hover p-5">
              <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-[var(--accent)] text-sm font-semibold text-white">
                1
              </span>
              <h3 className="mt-3 text-lg font-semibold">Create your account</h3>
              <p className="mt-2 text-sm leading-relaxed text-[var(--fg-muted)]">
                Sign up with your email and password. Email verification stays on the existing path.
              </p>
              <div className="mt-4 space-y-2 rounded-xl border border-[var(--border)] bg-[var(--bg)]/40 p-3">
                {["Name", "Email", "Password"].map((field) => (
                  <div
                    key={field}
                    className="h-9 rounded-md border border-[var(--border)] bg-[var(--surface-2)]/60 px-3 text-xs leading-9 text-[var(--fg-subtle)]"
                  >
                    {field}
                  </div>
                ))}
                <div className="h-9 rounded-md bg-[var(--hot)]/90 text-center text-xs font-semibold leading-9 text-white">
                  Create account
                </div>
              </div>
            </li>
            <li className="qf-glass-card qf-glass-card--hover p-5">
              <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-[var(--accent)] text-sm font-semibold text-white">
                2
              </span>
              <h3 className="mt-3 text-lg font-semibold">Connect your broker</h3>
              <p className="mt-2 text-sm leading-relaxed text-[var(--fg-muted)]">
                Enter the Weltrade MT5 login you own. QuantForg uses the permissions that account
                grants.
              </p>
              <div className="mt-4 flex flex-col items-center gap-3 rounded-xl border border-[var(--border)] bg-[var(--bg)]/40 p-4">
                <WeltradeLogo size={56} variant="wordmark" className="rounded-2xl" />
                <p className="text-xs font-semibold uppercase tracking-wide text-[var(--hot)]">
                  Primary Broker
                </p>
                <div className="flex flex-wrap justify-center gap-2">
                  {["MetaTrader 5", "IC Markets", "Exness", "Pepperstone", "XM"].map((name) => (
                    <span
                      key={name}
                      className="rounded-full border border-[var(--border)] bg-[var(--surface-2)] px-2.5 py-1 text-[10px] text-[var(--fg-muted)]"
                    >
                      {name}
                    </span>
                  ))}
                </div>
              </div>
            </li>
            <li className="qf-glass-card qf-glass-card--hover p-5">
              <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-[var(--accent)] text-sm font-semibold text-white">
                3
              </span>
              <h3 className="mt-3 text-lg font-semibold">Verify &amp; activate</h3>
              <p className="mt-2 text-sm leading-relaxed text-[var(--fg-muted)]">
                Confirm the session is connected, review risk status, then allow execution only if
                you choose to.
              </p>
              <ul className="mt-4 space-y-2 rounded-xl border border-[var(--border)] bg-[var(--bg)]/40 p-3 text-sm">
                {[
                  "Account verification",
                  "Broker permissions",
                  "Risk controls reviewed",
                  "Ready to trade",
                ].map((item) => (
                  <li key={item} className="flex items-center gap-2 text-[var(--fg-muted)]">
                    <Check className="h-4 w-4 text-[var(--success)]" aria-hidden />
                    {item}
                  </li>
                ))}
              </ul>
              <p className="mt-3 inline-flex items-center gap-2 rounded-lg border border-[var(--success)]/30 bg-[var(--success-soft)] px-3 py-2 text-xs font-medium text-[var(--success)]">
                <ShieldCheck className="h-4 w-4" aria-hidden />
                Account Verified — Ready to Trade
              </p>
            </li>
          </ol>
        </section>

        <section id="robot" className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6">
          <SectionTitle
            kicker="Workflow"
            title="What Your Robot Does"
            body="From market analysis to a broker-confirmed trade. Each stage stays distinct, and a later stage does not happen unless the earlier checks pass."
          />
          <ol className="flex flex-col gap-2 lg:flex-row lg:flex-wrap lg:items-stretch">
            {ROBOT.map((step, index) => (
              <li key={step.title} className="flex min-w-0 flex-1 items-stretch gap-2">
                <div className="qf-glass-card min-w-0 flex-1 p-3">
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-[var(--accent)]">
                    {String(index + 1).padStart(2, "0")}
                  </p>
                  <h3 className="mt-1 text-sm font-semibold">{step.title}</h3>
                  <p className="mt-1 text-xs leading-relaxed text-[var(--fg-muted)]">{step.body}</p>
                </div>
                {index < ROBOT.length - 1 ? (
                  <ChevronRight
                    className="mt-6 hidden h-4 w-4 shrink-0 text-[var(--fg-subtle)] lg:block"
                    aria-hidden
                  />
                ) : null}
              </li>
            ))}
          </ol>
        </section>

        <section id="strategies" className="mx-auto w-full max-w-6xl px-4 py-12 sm:px-6">
          <SectionTitle
            kicker="Strategy intelligence"
            title="Modules the product already evaluates"
            body="These names come from the existing strategy catalogue. Listing a module here does not mean it is taking trades."
          />
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {STRATEGIES.map((name) => (
              <li
                key={name}
                className="qf-glass-card qf-glass-card--hover p-4"
              >
                <Workflow className="mb-2 h-4 w-4 text-[var(--accent)]" aria-hidden />
                <h3 className="font-semibold">{name}</h3>
                <p className="mt-1 text-sm text-[var(--fg-muted)]">
                  Evaluated through the existing strategy desk and risk gates.
                </p>
              </li>
            ))}
          </ul>
        </section>

        <section id="risk" className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6">
          <SectionTitle
            kicker="Risk and capital protection"
            title="Controls that run before an order"
            body="Saved owner limits are enforced before send. Numbers below mirror the live owner policy ceilings — not sample account results."
          />
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {RISK_CONTROLS.map(([title, value]) => (
              <li
                key={title}
                className="qf-glass-card qf-glass-card--hover p-4"
              >
                <p className="text-[11px] font-semibold uppercase tracking-wide text-[var(--hot)]">
                  {title}
                </p>
                <p className="mt-2 text-xl font-semibold tabular text-[var(--fg)]">{value}</p>
              </li>
            ))}
          </ul>
        </section>

        <section id="performance" className="mx-auto w-full max-w-6xl px-4 py-12 sm:px-6">
          <SectionTitle
            kicker="Performance and transparency"
            title="Real results stay inside the account"
            body="No sample statistics are shown here. Win rate, profit, and drawdown appear only from broker history after you connect."
          />
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {[
              "Total trades",
              "Win rate",
              "Net profit",
              "Profit factor",
              "Max drawdown",
              "Avg. trade",
              "Open positions",
              "Broker verified",
            ].map((label) => (
              <div
                key={label}
                className="qf-glass-card border-dashed p-4"
              >
                <p className="text-xs uppercase tracking-wide text-[var(--fg-subtle)]">{label}</p>
                <p className="mt-2 text-lg font-semibold">—</p>
                <p className="mt-1 text-xs text-[var(--fg-muted)]">
                  Shown from your broker session, not from this page.
                </p>
              </div>
            ))}
          </div>
        </section>

        <section className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6">
          <SectionTitle
            kicker="Why QuantForg is different"
            title="Built around the account you connect"
            body="Weltrade through MetaTrader 5 is the production broker path. Other MT5 brands appear for context only."
          />
          <div className="mb-6 flex flex-wrap items-center gap-3">
            <WeltradeLogo size={48} variant="wordmark" className="rounded-xl" />
            {MT5_BROKERS.map((name) => (
              <span
                key={name}
                className="rounded-full border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-xs font-medium text-[var(--fg-muted)]"
              >
                {name}
              </span>
            ))}
          </div>
          <ul className="grid gap-3 md:grid-cols-2">
            {[
              "Your capital stays at your broker. QuantForg does not custody funds.",
              "Market analysis, a research signal, an approved order, and a confirmed fill are separate states.",
              "Risk controls run before order execution.",
              "The robot monitors positions and protective stops according to the settings already saved.",
            ].map((item) => (
              <li
                key={item}
                className="qf-glass-card flex gap-3 p-4 text-sm text-[var(--fg-muted)]"
              >
                <Check className="mt-0.5 h-4 w-4 shrink-0 text-[var(--success)]" aria-hidden />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </section>

        <section id="brokers" className="mx-auto w-full max-w-6xl px-4 py-12 sm:px-6">
          <SectionTitle
            kicker="Broker integration"
            title="Supported connection"
            body="Weltrade through MetaTrader 5 is the production broker path."
          />
          <div className="grid gap-3 sm:grid-cols-2">
            <article className="qf-glass-card qf-glass-card--hover p-5">
              <WeltradeLogo size={44} variant="wordmark" className="mb-3 rounded-xl" />
              <h3 className="text-lg font-semibold">Weltrade</h3>
              <p className="mt-2 text-sm text-[var(--fg-muted)]">
                Connect the real account you own. The Broker Accounts screen shows login, server,
                balance, and sync status from that session.
              </p>
            </article>
            <article className="qf-glass-card qf-glass-card--hover p-5">
              <CircleDollarSign className="mb-3 h-5 w-5 text-[var(--accent)]" aria-hidden />
              <h3 className="text-lg font-semibold">MetaTrader 5</h3>
              <p className="mt-2 text-sm text-[var(--fg-muted)]">
                Orders, positions, and history travel through the existing gateway. A disconnected
                gateway shows an unavailable state.
              </p>
            </article>
          </div>
        </section>

        <section id="security" className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6">
          <SectionTitle
            kicker="Security and reliability"
            title="Your account and the checks around it"
            body="Sign-in, broker connection, and order permission stay on the systems that already exist."
          />
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {SECURITY.map((item) => {
              const Icon = item.icon;
              return (
                <article
                  key={item.title}
                  className="qf-glass-card qf-glass-card--hover p-4"
                >
                  <Icon className="mb-3 h-5 w-5 text-[var(--success)]" aria-hidden />
                  <h3 className="font-semibold">{item.title}</h3>
                  <p className="mt-1 text-sm text-[var(--fg-muted)]">{item.body}</p>
                </article>
              );
            })}
          </div>
        </section>

        <section id="faq" className="mx-auto w-full max-w-6xl px-4 py-12 sm:px-6">
          <SectionTitle
            kicker="Questions"
            title="Frequently Asked Questions"
            body="Short answers about connection, symbols, results, and what the robot is allowed to do."
          />
          <FaqList />
        </section>

        <section className="mx-auto w-full max-w-6xl px-4 pb-16 sm:px-6">
          <div className="qf-glass-card qf-glass-card--hero relative overflow-hidden px-6 py-10 sm:px-10">
            <MountainBackdrop className="rounded-[1.25rem]" intensity="vivid" />
            <div className="relative grid items-center gap-8 lg:grid-cols-[1.2fr_0.8fr]">
              <div>
                <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">
                  Ready to Trade <span className="text-[var(--accent)]">Smarter?</span>
                </h2>
                <p className="mt-3 max-w-2xl text-sm leading-relaxed text-[var(--fg-muted)] sm:text-base">
                  Start with a subscription plan, create your account, and connect your broker when
                  you are ready. Trading results are never guaranteed.
                </p>
                <div className="mt-6 flex flex-wrap gap-3">
                  <Link href="/register" className={`${btn} qf-btn-cta h-11 px-5`}>
                    Connect Your Broker
                    <ArrowRight className="h-4 w-4" aria-hidden />
                  </Link>
                  <Link
                    href="/pricing"
                    className={`${btn} qf-glass-card h-11 border-0 px-5`}
                  >
                    View Pricing
                  </Link>
                </div>
              </div>
              <div className="hidden lg:block">
                <TerminalPreview />
              </div>
            </div>
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}
