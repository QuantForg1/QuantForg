import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import {
  Activity,
  ArrowRight,
  BarChart3,
  Brain,
  Check,
  ChevronRight,
  CircleCheck,
  Gauge,
  Lock,
  Monitor,
  Play,
  Radar,
  ScanSearch,
  Send,
  Shield,
  ShieldCheck,
  Sparkles,
  Workflow,
  Zap,
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
import styles from "./home-landing.module.css";

const btn =
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-[var(--radius-sm)] text-sm font-semibold transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg)]";

const CAPABILITIES: ReadonlyArray<{
  title: string;
  body: string;
  icon: LucideIcon;
}> = [
  {
    title: "MT5 Connectivity",
    body: "Secure connection to the MetaTrader 5 account you authorize.",
    icon: Monitor,
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
    icon: Zap,
  },
];

const ROBOT: ReadonlyArray<{
  title: string;
  body: string;
  icon: LucideIcon;
}> = [
  {
    title: "Market Scanning",
    body: "Reads the gold feed from the connected gateway.",
    icon: ScanSearch,
  },
  {
    title: "AI Analysis",
    body: "Scores structure, momentum, and context. A signal is not an order.",
    icon: Brain,
  },
  {
    title: "Strategy Engine",
    body: "Evaluates modules already in the product catalogue.",
    icon: Workflow,
  },
  {
    title: "Risk Validation",
    body: "Blocks orders that fail planned risk or spread limits before send.",
    icon: ShieldCheck,
  },
  {
    title: "Order Execution",
    body: "Sends approved orders through OMS and MT5. An order is not a fill.",
    icon: Send,
  },
  {
    title: "Trade Management",
    body: "Monitors open positions and protective stops on the connected account.",
    icon: Activity,
  },
  {
    title: "Trade Closure",
    body: "Closes or updates only through the broker connection.",
    icon: CircleCheck,
  },
  {
    title: "Performance",
    body: "History is the broker’s deals — never invented for this page.",
    icon: BarChart3,
  },
];

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

const SECURITY: ReadonlyArray<{
  title: string;
  body: string;
  icon: LucideIcon;
}> = [
  {
    title: "Encrypted Credentials",
    body: "Passwords are entered to sign in or connect. They are not printed back on the screen.",
    icon: Lock,
  },
  {
    title: "Secure Connection",
    body: "The existing MT5 gateway talks to the server on the account you connect.",
    icon: Radar,
  },
  {
    title: "Account-Level Permissions",
    body: "Trading uses the rights on that broker login. A missing permission stops the action.",
    icon: ShieldCheck,
  },
  {
    title: "Independent Risk Controls",
    body: "The risk engine can refuse an order before it reaches the broker.",
    icon: Shield,
  },
];

const MT5_CONTEXT = [
  "MetaTrader 5",
  "Weltrade",
  "XM",
  "Exness",
  "HFM",
  "JustMarkets",
  "IC Markets",
  "Pepperstone",
  "FP Markets",
] as const;

const PERFORMANCE_METRICS = [
  "Total trades",
  "Win rate",
  "Net profit",
  "Profit factor",
  "Max drawdown",
  "Average trade",
  "Open positions",
  "Broker verified",
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

function Sparkline({ seed }: { seed: number }) {
  const points = Array.from({ length: 8 }, (_, i) => {
    const y = 14 - ((seed * 7 + i * 11) % 12);
    return `${4 + i * 5},${y}`;
  }).join(" ");
  return (
    <svg className={styles.spark} viewBox="0 0 44 20" aria-hidden>
      <polyline
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={points}
      />
    </svg>
  );
}

function TerminalPreview({ tilted = false }: { tilted?: boolean }) {
  return (
    <div className={`${styles.laptop}${tilted ? ` ${styles.ctaLaptop}` : ""}`}>
      <div className={styles.laptopGlow} aria-hidden />
      <div className={styles.laptopBody}>
        <div className={styles.laptopBezel}>
          <div className={styles.laptopScreen}>
            <div className={styles.laptopChrome}>
              <span className={`${styles.dot} ${styles.dotRed}`} />
              <span className={`${styles.dot} ${styles.dotAmber}`} />
              <span className={`${styles.dot} ${styles.dotGreen}`} />
              <span className="ml-2 text-[10px] text-[var(--fg-subtle)]">
                Live Trading Terminal
              </span>
            </div>
            <div className={styles.terminalGrid}>
              <aside className={styles.terminalNav} aria-hidden>
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
                    className={i === 0 ? styles.terminalNavActive : styles.terminalNavItem}
                  >
                    {item}
                  </p>
                ))}
              </aside>
              <div className={styles.terminalMain}>
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs font-semibold">XAUUSD (Gold)</p>
                  <span className="inline-flex items-center gap-1 rounded-full border border-[var(--border)] bg-[var(--surface)]/70 px-2 py-0.5 text-[10px] text-[var(--fg-muted)]">
                    Preview
                  </span>
                </div>
                <div
                  className={styles.chartFrame}
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
                <dl className={styles.metricGrid}>
                  {[
                    ["Account Equity", "—"],
                    ["Open Positions", "—"],
                    ["Today’s P&L", "—"],
                    ["Win Rate", "—"],
                  ].map(([label, value]) => (
                    <div
                      key={label}
                      className="rounded-md border border-[var(--border)] bg-[var(--bg)]/40 px-2 py-1.5 text-[10px]"
                    >
                      <dt className="text-[var(--fg-subtle)]">{label}</dt>
                      <dd className="mt-0.5 font-medium text-[var(--fg)]">{value}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            </div>
          </div>
        </div>
        <div className={styles.laptopBase} aria-hidden />
      </div>
    </div>
  );
}

export function HomeLanding() {
  return (
    <div className={styles.page}>
      <div className={styles.atmosphere} aria-hidden>
        <MountainBackdrop intensity="soft" />
      </div>
      <div className={styles.shell}>
        <SiteHeader active="home" />
        <main id="main-content" tabIndex={-1}>
          <section id="platform" className={styles.hero}>
            <MountainBackdrop withCandles intensity="vivid" />
            <div className={`${styles.section} ${styles.heroGrid}`}>
              <div>
                <p className={styles.badge}>
                  <Sparkles className="h-3.5 w-3.5 text-[var(--accent)]" aria-hidden />
                  Institutional AI Trading · MT5 · 24/5 gold session
                </p>
                <h1 className={styles.headline}>
                  Your Trading.
                  <span className="mt-1 block">Our Intelligence.</span>
                  <span className={`mt-1 block ${styles.headlineAccent}`}>Fully Connected.</span>
                </h1>
                <p className={styles.lead}>
                  QuantForg is an Institutional AI Trading Platform that connects traders to their
                  broker accounts and provides market intelligence, strategy evaluation, risk
                  management, and automated execution under approved settings. Software access is
                  not a promise of profits.
                </p>
                <div className={styles.ctaRow}>
                  <Link href="/register" className={`${btn} qf-btn-cta h-12 px-5`}>
                    Connect Your Broker
                    <ArrowRight className="h-4 w-4" aria-hidden />
                  </Link>
                  <Link
                    href="/#how-it-works"
                    className={`${btn} ${styles.secondaryBtn} h-12 px-5`}
                  >
                    <Play className="h-4 w-4 text-[var(--accent)]" aria-hidden />
                    Explore How It Works
                  </Link>
                </div>
                <ul className={styles.trustRow}>
                  {[
                    "Works with your MT5 broker.",
                    "Your capital, your control.",
                    "Risk checks before every order.",
                  ].map((item) => (
                    <li key={item} className={styles.trustItem}>
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
            className={`${styles.section} ${styles.featureGrid}`}
            aria-label="Platform capabilities"
          >
            {CAPABILITIES.map((item) => {
              const Icon = item.icon;
              return (
                <article key={item.title} className={`qf-glass-card qf-glass-card--hover ${styles.featureCard}`}>
                  <span className={styles.featureIcon}>
                    <Icon className="h-5 w-5" aria-hidden />
                  </span>
                  <h2 className="text-base font-semibold">{item.title}</h2>
                  <p className="mt-1 text-sm text-[var(--fg-muted)]">{item.body}</p>
                </article>
              );
            })}
          </section>

          <section id="how-it-works" className={`${styles.section} py-12`}>
            <SectionTitle
              kicker="Get started"
              title="How to Connect Your Broker — 3 Simple Steps"
              body="You connect the account you already have. QuantForg does not open a broker account for you."
            />
            <ol className={styles.steps}>
              <li className="qf-glass-card qf-glass-card--hover p-5">
                <span className={styles.stepNumber}>1</span>
                <h3 className="mt-3 text-lg font-semibold">Create your account</h3>
                <p className="mt-2 text-sm leading-relaxed text-[var(--fg-muted)]">
                  Sign up with your email and password. Email verification stays on the existing
                  path.
                </p>
                <div className={styles.formPreview} aria-hidden>
                  {["Name", "Email", "Password"].map((field) => (
                    <div key={field} className={styles.formField}>
                      {field}
                    </div>
                  ))}
                </div>
                <Link href="/register" className={`${styles.formCta} mt-2 w-full`}>
                  Create account
                </Link>
              </li>
              <li className="qf-glass-card qf-glass-card--hover p-5">
                <span className={styles.stepNumber}>2</span>
                <h3 className="mt-3 text-lg font-semibold">Connect your broker</h3>
                <p className="mt-2 text-sm leading-relaxed text-[var(--fg-muted)]">
                  Enter the Weltrade MT5 login you own. QuantForg uses the permissions that account
                  grants.
                </p>
                <div className="mt-4 flex flex-col items-center gap-3 rounded-xl border border-[var(--border)] bg-[var(--bg)]/40 p-4">
                  <WeltradeLogo size={56} variant="wordmark" className="rounded-2xl" />
                  <p className="text-xs font-semibold uppercase tracking-wide text-[var(--accent)]">
                    Primary Broker
                  </p>
                  <p className="text-center text-[10px] text-[var(--fg-subtle)]">
                    Other names below are MT5 compatibility context only — not verified production
                    integrations.
                  </p>
                  <div className={styles.brokerChipRow}>
                    {MT5_CONTEXT.map((name) => (
                      <span key={name} className={styles.brokerChip}>
                        {name}
                      </span>
                    ))}
                  </div>
                </div>
              </li>
              <li className="qf-glass-card qf-glass-card--hover p-5">
                <span className={styles.stepNumber}>3</span>
                <h3 className="mt-3 text-lg font-semibold">Verify and activate</h3>
                <p className="mt-2 text-sm leading-relaxed text-[var(--fg-muted)]">
                  Confirm the session is connected, review risk status, then allow execution only if
                  you choose to.
                </p>
                <ul className="mt-4 space-y-2 rounded-xl border border-[var(--border)] bg-[var(--bg)]/40 p-3 text-sm">
                  {[
                    "Account verification",
                    "Broker permissions",
                    "Risk controls reviewed",
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

          <section id="robot" className={`${styles.section} py-6`}>
            <SectionTitle
              kicker="Workflow"
              title="What Your Robot Does"
              body="From market analysis to a broker-confirmed trade. A signal is not an order. An order is not a confirmed fill. Risk validation occurs before execution. Performance comes from actual broker history."
            />
            <ol className={styles.robotRow}>
              {ROBOT.map((step, index) => {
                const Icon = step.icon;
                return (
                  <li key={step.title} className={styles.robotItem}>
                    <div className={`qf-glass-card ${styles.robotCard}`}>
                      <div className="mb-2 flex items-center justify-between gap-2">
                        <p className="text-[10px] font-semibold uppercase tracking-wide text-[var(--accent)]">
                          {String(index + 1).padStart(2, "0")}
                        </p>
                        <Icon className="h-3.5 w-3.5 text-[var(--accent)]" aria-hidden />
                      </div>
                      <h3 className="text-sm font-semibold">{step.title}</h3>
                      <p className="mt-1 text-xs leading-relaxed text-[var(--fg-muted)]">
                        {step.body}
                      </p>
                    </div>
                    {index < ROBOT.length - 1 ? (
                      <ChevronRight className={styles.robotArrow} aria-hidden />
                    ) : null}
                  </li>
                );
              })}
            </ol>
          </section>

          <section id="strategies" className={`${styles.section} py-12`}>
            <SectionTitle
              kicker="Strategy intelligence"
              title="Modules the product already evaluates"
              body="These names come from the existing strategy catalogue. Listing a module here does not mean it is currently active or executing trades."
            />
            <ul className={styles.strategyGrid}>
              {STRATEGIES.map((name, index) => (
                <li key={name} className={`qf-glass-card qf-glass-card--hover ${styles.strategyPill}`}>
                  <Sparkline seed={index + 3} />
                  <div>
                    <h3 className="font-semibold">{name}</h3>
                    <p className="mt-0.5 text-xs text-[var(--fg-muted)]">Catalogue module</p>
                  </div>
                </li>
              ))}
            </ul>
          </section>

          <section id="risk" className={`${styles.section} py-6`}>
            <SectionTitle
              kicker="Risk and capital protection"
              title="Controls that run before an order"
              body="Saved owner limits are enforced before send. Numbers below mirror the live owner policy ceilings — not sample account results."
            />
            <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {RISK_CONTROLS.map(([title, value]) => (
                <li key={title} className="qf-glass-card qf-glass-card--hover p-4">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-[var(--fg-subtle)]">
                    {title}
                  </p>
                  <p className={styles.riskValue}>{value}</p>
                </li>
              ))}
            </ul>
          </section>

          <section id="performance" className={`${styles.section} py-12`}>
            <SectionTitle
              kicker="Performance and transparency"
              title="Real results stay inside the account"
              body="No sample statistics are shown here. Win rate, profit, and drawdown appear only from broker history after you connect."
            />
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {PERFORMANCE_METRICS.map((label) => (
                <div key={label} className="qf-glass-card border-dashed p-4">
                  <p className="text-xs uppercase tracking-wide text-[var(--fg-subtle)]">{label}</p>
                  <p className="mt-2 text-lg font-semibold">—</p>
                  <p className="mt-1 text-xs text-[var(--fg-muted)]">
                    Shown from your broker session, not from this page.
                  </p>
                </div>
              ))}
            </div>
          </section>

          <section className={`${styles.section} py-6`}>
            <SectionTitle
              kicker="Why QuantForg is different"
              title="Built around the account you connect"
              body="Your capital stays at your broker. Market analysis, research signals, approved orders, and confirmed fills are distinct. Risk controls run before execution. The robot monitors positions and protective stops."
            />
            <div className={styles.diffGrid}>
              <article className="qf-glass-card p-5">
                <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-[var(--accent)]">
                  Broker context
                </p>
                <div className="mb-4 flex items-center gap-3">
                  <WeltradeLogo size={48} variant="wordmark" className="rounded-xl" />
                  <div>
                    <p className="text-sm font-semibold">Weltrade</p>
                    <p className="text-xs text-[var(--fg-muted)]">Production broker path</p>
                  </div>
                </div>
                <div className={styles.brokerChipRow}>
                  {MT5_CONTEXT.map((name) => (
                    <span key={name} className={styles.brokerChip}>
                      {name}
                    </span>
                  ))}
                </div>
                <p className="mt-3 text-xs text-[var(--fg-subtle)]">
                  Non-Weltrade names are contextual MT5 references only.
                </p>
              </article>
              <article className="qf-glass-card p-5">
                <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-[var(--accent)]">
                  Operating principles
                </p>
                <ul className="space-y-3">
                  {[
                    "Your capital stays at your broker. QuantForg does not custody funds.",
                    "Market analysis, a research signal, an approved order, and a confirmed fill are separate states.",
                    "Risk controls run before order execution.",
                    "The robot monitors positions and protective stops according to the settings already saved.",
                  ].map((item) => (
                    <li key={item} className="flex gap-3 text-sm text-[var(--fg-muted)]">
                      <Check className="mt-0.5 h-4 w-4 shrink-0 text-[var(--success)]" aria-hidden />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </article>
            </div>
          </section>

          <section id="brokers" className={`${styles.section} py-12`}>
            <SectionTitle
              kicker="Broker integration"
              title="Supported connection"
              body="Weltrade through MetaTrader 5 is the production broker path."
            />
            <div className={styles.brokerGrid}>
              <article className="qf-glass-card qf-glass-card--hover p-5">
                <WeltradeLogo size={44} variant="wordmark" className="mb-3 rounded-xl" />
                <h3 className="text-lg font-semibold">Weltrade</h3>
                <p className="mt-2 text-sm text-[var(--fg-muted)]">
                  Connect the real account you own. The Broker Accounts screen shows login, server,
                  balance, and sync status from that session.
                </p>
              </article>
              <article className="qf-glass-card qf-glass-card--hover p-5">
                <Gauge className="mb-3 h-5 w-5 text-[var(--accent)]" aria-hidden />
                <h3 className="text-lg font-semibold">MetaTrader 5</h3>
                <p className="mt-2 text-sm text-[var(--fg-muted)]">
                  Orders, positions, and history travel through the existing gateway. A disconnected
                  gateway shows an unavailable state.
                </p>
              </article>
            </div>
          </section>

          <section id="security" className={`${styles.section} py-6`}>
            <SectionTitle
              kicker="Security and reliability"
              title="Your account and the checks around it"
              body="Sign-in, broker connection, and order permission stay on the systems that already exist. No unsupported security certifications are claimed here."
            />
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {SECURITY.map((item) => {
                const Icon = item.icon;
                return (
                  <article key={item.title} className="qf-glass-card qf-glass-card--hover p-4">
                    <Icon className="mb-3 h-5 w-5 text-[var(--accent)]" aria-hidden />
                    <h3 className="font-semibold">{item.title}</h3>
                    <p className="mt-1 text-sm text-[var(--fg-muted)]">{item.body}</p>
                  </article>
                );
              })}
            </div>
          </section>

          <section id="faq" className={`${styles.section} py-6`}>
            <SectionTitle
              kicker="Questions"
              title="Frequently Asked Questions"
              body="Short answers about connection, symbols, results, and what the robot is allowed to do."
            />
            <FaqList />
          </section>

          <section className={`${styles.section} pb-16 pt-6`}>
            <div className={`qf-glass-card qf-glass-card--hero ${styles.ctaBand}`}>
              <MountainBackdrop className="rounded-[1.25rem]" intensity="vivid" />
              <div className={styles.ctaGrid}>
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
                    <Link href="/pricing" className={`${btn} ${styles.secondaryBtn} h-11 px-5`}>
                      View Pricing
                    </Link>
                  </div>
                </div>
                <TerminalPreview tilted />
              </div>
            </div>
          </section>
        </main>
        <SiteFooter />
      </div>
    </div>
  );
}
