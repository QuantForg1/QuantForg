import Link from "next/link";
import {
  ArrowRight,
  Brain,
  Cable,
  LineChart,
  Check,
  CircleDollarSign,
  Clock,
  Lock,
  Play,
  Radar,
  Shield,
  ShieldCheck,
  Sparkles,
  Workflow,
} from "lucide-react";
import { SiteFooter } from "@/components/marketing/site-footer";
import { SiteHeader } from "@/components/marketing/site-header";
import { FaqList } from "@/components/marketing/faq-list";
import { AUTO_STRATEGY_MODULES } from "@/lib/auto-trading/strategy-modules";

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

const STEPS = [
  {
    n: "1",
    title: "Create your account",
    body: "Sign up with your email and password. Email verification stays on the existing path.",
  },
  {
    n: "2",
    title: "Connect your broker",
    body: "Enter the Weltrade MT5 login you own. QuantForg uses the permissions that account grants.",
  },
  {
    n: "3",
    title: "Verify and activate",
    body: "Confirm the session is connected, review risk status, then allow execution only if you choose to.",
  },
] as const;

const ROBOT = [
  { title: "Market Scanning", body: "Reads the gold feed from the connected gateway." },
  { title: "AI Analysis", body: "Scores structure, momentum, and context. Advisory until a gate passes." },
  { title: "Strategy Engine", body: "Evaluates the modules already in the product. It does not invent a new strategy." },
  { title: "Risk Validation", body: "Blocks the order when planned risk, spread, quality, or loss limits fail." },
  { title: "Order Execution", body: "Sends an approved order through the existing OMS and MT5 path." },
  { title: "Trade Management", body: "Monitors an open position and the protective stops already attached." },
  { title: "Trade Closure", body: "Closes or updates only through the same broker connection." },
  { title: "Performance", body: "History is the broker’s deals. Missing history stays empty." },
] as const;

const RISK_CONTROLS = [
  ["Planned risk", "Per-trade ceiling checked before send."],
  ["Aggregate open risk", "Cap on combined open exposure."],
  ["Minimum net reward/risk", "Trades below the saved floor are rejected."],
  ["Trade quality", "Minimum score from the existing quality gate."],
  ["Maximum lot", "Size ceiling for a single order."],
  ["Maximum spread", "Entries stop when the spread is too wide."],
  ["Daily loss halt", "New entries stop when the saved daily loss is reached."],
  ["Symbol allowlist", "The live desk is XAUUSD (Gold)."],
  ["Concurrent positions", "Limits how many positions can be open together."],
  ["ATR stop", "Protective stop distance uses the saved ATR multiplier."],
] as const;

const DIFFERENCE = [
  "Your capital stays at your broker. QuantForg does not custody funds.",
  "Market analysis, a research signal, an approved order, and a confirmed fill are separate states.",
  "Risk controls run before order execution.",
  "The robot monitors positions and protective stops according to the settings already saved.",
  "This page does not show sample account balances, win rates, or backtests.",
] as const;

const SECURITY = [
  {
    title: "Credentials stay private",
    body: "Passwords are entered to sign in or connect. They are not printed back on the screen.",
    icon: Lock,
  },
  {
    title: "Broker connection",
    body: "The existing MT5 gateway talks to the server on the account you connect.",
    icon: Cable,
  },
  {
    title: "Account permissions",
    body: "Trading uses the rights on that broker login. A missing permission stops the action.",
    icon: ShieldCheck,
  },
  {
    title: "Independent risk checks",
    body: "The risk engine can refuse an order before it reaches the broker.",
    icon: Shield,
  },
] as const;

function SectionTitle({
  id,
  kicker,
  title,
  body,
  action,
}: {
  id?: string;
  kicker: string;
  title: string;
  body: string;
  action?: { href: string; label: string };
}) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--hot)]">{kicker}</p>
        <h2 id={id} className="mt-1 text-2xl font-semibold tracking-tight text-[var(--fg)] sm:text-3xl">
          {title}
        </h2>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-[var(--fg-muted)]">{body}</p>
      </div>
      {action ? (
        <Link href={action.href} className="text-sm font-medium text-[var(--accent)] hover:underline">
          {action.label}
        </Link>
      ) : null}
    </div>
  );
}

export function HomeLanding() {
  return (
    <div className="min-h-screen overflow-x-clip bg-[var(--bg)] text-[var(--fg)]">
      <SiteHeader active="home" />
      <main id="main-content" tabIndex={-1}>
        <section id="platform" className="relative overflow-hidden">
          <div
            className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_20%_20%,rgba(255,122,69,0.16),transparent_42%),radial-gradient(ellipse_at_80%_0%,rgba(22,139,255,0.22),transparent_46%),linear-gradient(180deg,#0c3c72_0%,#061a38_72%)]"
            aria-hidden
          />
          <div className="relative mx-auto grid w-full max-w-6xl items-center gap-10 px-4 py-14 sm:px-6 lg:grid-cols-[1.05fr_0.95fr] lg:py-20">
            <div>
              <p className="inline-flex items-center gap-2 rounded-full border border-[var(--border)] bg-[var(--surface)]/70 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-muted)]">
                <Sparkles className="h-3.5 w-3.5 text-[var(--accent)]" aria-hidden />
                AI powered · MT5 · Institutional grade
              </p>
              <h1 className="mt-5 font-[family-name:var(--font-display)] text-4xl leading-[1.05] tracking-tight sm:text-6xl">
                Your Trading.
                <span className="mt-1 block">Our Intelligence.</span>
                <span className="mt-1 block text-[var(--hot)]">Fully Connected.</span>
                <span className="sr-only"> Institutional trading terminal.</span>
              </h1>
              <p className="mt-5 max-w-xl text-base leading-relaxed text-[var(--fg-muted)] sm:text-lg">
                Connect your broker. QuantForg analyzes the gold market, identifies research
                opportunities, manages risk, and can execute only under the settings already
                approved for your account.
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <Link href="/register" className={`${btn} qf-btn-hot h-12 px-5`}>
                  Connect Your Broker
                  <ArrowRight className="h-4 w-4" aria-hidden />
                </Link>
                <Link
                  href="/#how-it-works"
                  className={`${btn} h-12 border border-[var(--border-strong)] bg-[var(--surface)]/60 px-5 text-[var(--fg)] hover:bg-[var(--surface-2)]`}
                >
                  <Play className="h-4 w-4" aria-hidden />
                  Explore How It Works
                </Link>
              </div>
              <ul className="mt-6 flex flex-col gap-2 text-sm text-[var(--fg-muted)] sm:flex-row sm:flex-wrap sm:gap-x-5">
                <li className="inline-flex items-center gap-2">
                  <Check className="h-4 w-4 text-[var(--success)]" aria-hidden />
                  Works with your MT5 broker
                </li>
                <li className="inline-flex items-center gap-2">
                  <Check className="h-4 w-4 text-[var(--success)]" aria-hidden />
                  Your capital, your control
                </li>
                <li className="inline-flex items-center gap-2">
                  <Check className="h-4 w-4 text-[var(--success)]" aria-hidden />
                  Risk checks before every order
                </li>
              </ul>
            </div>
            <div className="rounded-[1.25rem] border border-[var(--border-strong)] bg-[var(--bg-elevated)]/90 p-3 shadow-[var(--shadow-elevated)]">
              <div className="rounded-[1rem] border border-[var(--border)] bg-[var(--surface)] p-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-medium">Live Trading Terminal</p>
                  <span className="rounded-full border border-[var(--border)] px-2 py-0.5 text-[11px] text-[var(--fg-muted)]">
                    Preview
                  </span>
                </div>
                <p className="mt-1 text-xs text-[var(--fg-subtle)]">
                  Layout only. Prices, equity, and P&amp;L appear after your broker session connects.
                </p>
                <div className="mt-4 flex items-end gap-1" role="img" aria-label="Decorative chart frame, not a price history">
                  {Array.from({ length: 28 }, (_, i) => {
                    const up = i % 3 !== 0;
                    const body = 18 + ((i * 17) % 42);
                    return (
                      <span key={i} className="flex flex-1 flex-col items-center justify-end" style={{ height: 120 }}>
                        <span
                          className={up ? "w-2 rounded-sm bg-[var(--success)]/80" : "w-2 rounded-sm bg-[var(--danger)]/80"}
                          style={{ height: body }}
                        />
                      </span>
                    );
                  })}
                </div>
                <dl className="mt-4 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
                  {[
                    ["Symbol", "XAUUSD"],
                    ["Account equity", "—"],
                    ["Open positions", "—"],
                    ["Today's P&L", "—"],
                  ].map(([label, value]) => (
                    <div key={label} className="rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--bg)]/50 px-3 py-2">
                      <dt className="text-[11px] uppercase tracking-wide text-[var(--fg-subtle)]">{label}</dt>
                      <dd className="mt-1 font-medium">{value}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            </div>
          </div>
        </section>

        <section id="features" className="mx-auto grid w-full max-w-6xl gap-3 px-4 py-8 sm:grid-cols-2 sm:px-6 lg:grid-cols-4" aria-label="Platform capabilities">
          {CAPABILITIES.map((item) => {
            const Icon = item.icon;
            return (
              <article key={item.title} className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] p-4">
                <Icon className="mb-3 h-5 w-5 text-[var(--accent)]" aria-hidden />
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
            {STEPS.map((step) => (
              <li key={step.n} className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] p-5">
                <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-[var(--accent)] text-sm font-semibold text-white">
                  {step.n}
                </span>
                <h3 className="mt-3 text-lg font-semibold">{step.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-[var(--fg-muted)]">{step.body}</p>
              </li>
            ))}
          </ol>
        </section>

        <section id="robot" className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6">
          <SectionTitle
            kicker="Workflow"
            title="What Your Robot Does"
            body="From market analysis to a broker-confirmed trade. Each stage stays distinct, and a later stage does not happen unless the earlier checks pass."
          />
          <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {ROBOT.map((step, index) => (
              <li key={step.title} className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--bg-elevated)] p-4">
                <p className="text-xs font-semibold text-[var(--accent)]">0{index + 1}</p>
                <h3 className="mt-2 font-semibold">{step.title}</h3>
                <p className="mt-1 text-sm text-[var(--fg-muted)]">{step.body}</p>
              </li>
            ))}
          </ol>
        </section>

        <section id="strategies" className="mx-auto w-full max-w-6xl px-4 py-12 sm:px-6">
          <SectionTitle
            kicker="Strategy intelligence"
            title="Modules the product already evaluates"
            body="These names come from the existing strategy catalogue. Listing a module here does not mean it is taking trades, and it does not add a new strategy."
            action={{ href: "/login", label: "Open strategies after sign-in" }}
          />
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {AUTO_STRATEGY_MODULES.map((module) => (
              <li key={module.id} className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] p-4">
                <Workflow className="mb-2 h-4 w-4 text-[var(--accent)]" aria-hidden />
                <h3 className="font-semibold">{module.label}</h3>
                <p className="mt-1 text-sm text-[var(--fg-muted)]">{module.hint}</p>
              </li>
            ))}
            <li className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] p-4">
              <Radar className="mb-2 h-4 w-4 text-[var(--accent)]" aria-hidden />
              <h3 className="font-semibold">ICT sweep templates</h3>
              <p className="mt-1 text-sm text-[var(--fg-muted)]">
                Bullish sweep, bearish sweep, and range watch are templates in the strategy desk. They still pass the same risk checks.
              </p>
            </li>
          </ul>
        </section>

        <section id="risk" className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6">
          <SectionTitle
            kicker="Risk and capital protection"
            title="Controls that run before an order"
            body="Saved limits are shown in Risk Center after you sign in. This page names the controls and does not publish a second copy of the numbers."
            action={{ href: "/risk-center", label: "View risk settings" }}
          />
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {RISK_CONTROLS.map(([title, body]) => (
              <li key={title} className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] p-4">
                <h3 className="text-sm font-semibold">{title}</h3>
                <p className="mt-1 text-xs leading-relaxed text-[var(--fg-muted)]">{body}</p>
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
            {["Total trades", "Win rate", "Net profit", "Open positions"].map((label) => (
              <div key={label} className="rounded-[var(--radius-os)] border border-dashed border-[var(--border-strong)] bg-[var(--bg-elevated)] p-4">
                <p className="text-xs uppercase tracking-wide text-[var(--fg-subtle)]">{label}</p>
                <p className="mt-2 text-lg font-semibold">Unavailable</p>
                <p className="mt-1 text-xs text-[var(--fg-muted)]">Shown from your broker session, not from this page.</p>
              </div>
            ))}
          </div>
        </section>

        <section className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6">
          <SectionTitle
            kicker="Why QuantForg is different"
            title="Built around the account you connect"
            body="The product is an institutional workspace for analysis, risk, and gated execution."
          />
          <ul className="grid gap-3 md:grid-cols-2">
            {DIFFERENCE.map((item) => (
              <li key={item} className="flex gap-3 rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] p-4 text-sm text-[var(--fg-muted)]">
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
            body="Weltrade through MetaTrader 5 is the production broker path. Other broker logos are not shown, because they are not connected."
          />
          <div className="grid gap-3 sm:grid-cols-2">
            <article className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] p-5">
              <LineChart className="mb-3 h-5 w-5 text-[var(--accent)]" aria-hidden />
              <h3 className="text-lg font-semibold">Weltrade</h3>
              <p className="mt-2 text-sm text-[var(--fg-muted)]">
                Connect the real account you own. The Broker Accounts screen shows login, server, balance, and sync status from that session.
              </p>
            </article>
            <article className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] p-5">
              <CircleDollarSign className="mb-3 h-5 w-5 text-[var(--accent)]" aria-hidden />
              <h3 className="text-lg font-semibold">MetaTrader 5</h3>
              <p className="mt-2 text-sm text-[var(--fg-muted)]">
                Orders, positions, and history travel through the existing gateway. A disconnected gateway shows an unavailable state.
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
                <article key={item.title} className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] p-4">
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
          <div className="overflow-hidden rounded-[1.25rem] border border-[var(--border)] bg-[linear-gradient(120deg,#0c3c72,#061a38_55%,#12345c)] px-6 py-10 sm:px-10">
            <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">
              Ready to Trade <span className="text-[var(--hot)]">Smarter?</span>
            </h2>
            <p className="mt-3 max-w-2xl text-sm leading-relaxed text-[var(--fg-muted)] sm:text-base">
              Connect your broker and let QuantForg handle analysis, risk checks, and execution under the settings you approve. Results are not guaranteed.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link href="/register" className={`${btn} qf-btn-hot h-11 px-5`}>
                Connect Your Broker
                <ArrowRight className="h-4 w-4" aria-hidden />
              </Link>
              <Link href="/pricing" className={`${btn} h-11 border border-[var(--border-strong)] px-5`}>
                View Pricing
              </Link>
            </div>
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}
