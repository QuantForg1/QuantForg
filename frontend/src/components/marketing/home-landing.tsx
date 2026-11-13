import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import {
  Activity,
  BarChart3,
  Brain,
  CandlestickChart,
  Check,
  Eye,
  FileLock2,
  Gauge,
  KeyRound,
  Layers,
  LineChart,
  Monitor,
  MoveUpRight,
  RefreshCcw,
  Send,
  Shield,
  ShieldCheck,
  Target,
  Unplug,
  Waves,
  Workflow,
  Zap,
} from "lucide-react";
import { FaqList } from "@/components/marketing/faq-list";
import { HomeHeader } from "@/components/marketing/home-header";
import { Reveal } from "@/components/marketing/reveal";
import { BrandLogo } from "@/components/brand/brand-logo";
import { MountainBackdrop } from "@/components/brand/mountain-backdrop";
import {
  ANNUAL_BILLING_SUPPORTED,
  BILLING_PLANS,
  BILLING_PROVIDER,
  formatUsd,
  TRIAL_DAYS,
  TRIAL_POSITIONING,
} from "@/lib/billing/plans";
import styles from "./home-landing.module.css";

const FEATURES: ReadonlyArray<{ title: string; body: string; icon: LucideIcon }> = [
  {
    title: "MT5 Connectivity",
    body: "Connect the MetaTrader 5 account you already own. Weltrade is the production path. The gateway reads that login’s session.",
    icon: Monitor,
  },
  {
    title: "AI Market Intelligence",
    body: "The gold desk scores structure, momentum, and context. A score is research. It is not an order.",
    icon: Brain,
  },
  {
    title: "Automated Risk Management",
    body: "Risk checks run before an order is handed to the broker. A failed check blocks the send.",
    icon: Shield,
  },
  {
    title: "Trading Execution",
    body: "Authorized orders go through the order path and MT5. An order is not a fill until the broker confirms it.",
    icon: Send,
  },
  {
    title: "Position Monitoring",
    body: "Open positions and protective stops are read from the connected account and watched while the session is up.",
    icon: Activity,
  },
  {
    title: "Performance Analytics",
    body: "Results come from broker deal history after you connect. This page does not publish sample statistics.",
    icon: BarChart3,
  },
];

const STEPS = [
  {
    n: "01",
    title: "Create Your Account",
    body: "Sign up with your email and password. Email verification stays on the existing account path. QuantForg does not add a separate identity check here.",
    href: "/register",
    label: "Create account",
  },
  {
    n: "02",
    title: "Connect Your Broker",
    body: "After sign-in, Broker Accounts takes the Weltrade MT5 login you own. QuantForg uses the permissions that account already grants.",
    href: "/brokers",
    label: "Open Broker Accounts",
  },
  {
    n: "03",
    title: "Verify & Activate",
    body: "Confirm the gateway session is connected and review risk status. Execution stays off until it is authorized. A connected login is not an automatic order.",
    href: "/#security",
    label: "Review the controls",
  },
] as const;

/** Homepage display only — logo + name. Does not change connection capability. */
const BROKERS: ReadonlyArray<{
  name: string;
  logoSrc: string;
}> = [
  { name: "Weltrade", logoSrc: "/brand/brokers/weltrade-logo.png" },
  { name: "XM", logoSrc: "/brand/brokers/xm-mark.png" },
  { name: "Exness", logoSrc: "/brand/brokers/exness-mark.png" },
  { name: "HFM", logoSrc: "/brand/brokers/hfm-mark.png" },
  { name: "JustMarkets", logoSrc: "/brand/brokers/justmarkets-mark.png" },
  { name: "IC Markets", logoSrc: "/brand/brokers/icmarkets-mark.png" },
  { name: "Pepperstone", logoSrc: "/brand/brokers/pepperstone-mark.png" },
  { name: "FP Markets", logoSrc: "/brand/brokers/fpmarkets-mark.svg" },
];

const WORKFLOW: ReadonlyArray<{ title: string; body: string }> = [
  { title: "Market Scanning", body: "Reads the gold feed from the connected gateway." },
  { title: "AI Analysis", body: "Scores structure, momentum, and context." },
  { title: "Strategy Evaluation", body: "Runs the profiles already in the strategy registry." },
  { title: "Risk Validation", body: "Blocks an order that fails the checks before send." },
  { title: "Order Execution", body: "Submits only an authorized order through MT5." },
  { title: "Trade Management", body: "Monitors open positions and protective stops." },
  { title: "Trade Closure", body: "Closes or updates only through the broker connection." },
  { title: "Performance Review", body: "Uses broker deal history. Nothing is invented here." },
];

const RULES = [
  "Analysis is not an order.",
  "A signal is not an executed trade.",
  "Risk validation happens before order submission.",
  "Execution requires authorization and broker connectivity.",
] as const;

const EXECUTION_PROFILES: ReadonlyArray<{
  title: string;
  status: string;
  body: string;
  icon: LucideIcon;
}> = [
  {
    title: "Trend Following",
    status: "Execution profile",
    body: "Trend continuation scalping. It can be selected only after risk and execution gates.",
    icon: MoveUpRight,
  },
  {
    title: "Breakout",
    status: "Execution profile",
    body: "Breakout scalping on volatility expansion. A setup is not a broker order.",
    icon: Zap,
  },
  {
    title: "Mean Reversion",
    status: "Execution profile",
    body: "Range mean-reversion scalping, used in range-like regimes.",
    icon: RefreshCcw,
  },
  {
    title: "Momentum",
    status: "Execution profile",
    body: "Momentum scalping. Directional confirmation still waits on risk validation.",
    icon: Gauge,
  },
  {
    title: "SMC Scalping",
    status: "Execution profile",
    body: "The production SMC profile. Liquidity sweep, order block, and fair value gap sit inside it.",
    icon: CandlestickChart,
  },
];

const ANALYSIS_FACTORS: ReadonlyArray<{
  title: string;
  status: string;
  body: string;
  icon: LucideIcon;
}> = [
  {
    title: "Liquidity Sweep",
    status: "Inside SMC",
    body: "A weight inside SMC Scalping. Not a separate execution profile.",
    icon: Waves,
  },
  {
    title: "Order Block",
    status: "Inside SMC",
    body: "A structure factor in SMC scoring. It is not submitted as its own order.",
    icon: Layers,
  },
  {
    title: "Fair Value Gap",
    status: "Inside SMC",
    body: "A gap factor in SMC scoring. Not its own strategy id.",
    icon: Target,
  },
  {
    title: "RSI",
    status: "Advisory vote",
    body: "Momentum oscillator advisory. Cannot win order selection on its own.",
    icon: Activity,
  },
  {
    title: "MACD",
    status: "Advisory vote",
    body: "Trend-momentum advisory vote. Not an independent execution profile.",
    icon: LineChart,
  },
  {
    title: "Bollinger Bands",
    status: "Advisory vote",
    body: "Volatility factor advisory. Vote only — not an execution profile.",
    icon: BarChart3,
  },
];

const RISK_ROWS = [
  {
    name: "Risk per trade",
    ceiling: "A platform ceiling is enforced before send.",
    preference: "Your preference can be stricter. It cannot raise the ceiling.",
  },
  {
    name: "Maximum lot",
    ceiling: "Volume is hard-capped by the platform maximum.",
    preference: "A personal maximum cannot exceed that cap.",
  },
  {
    name: "Spread protection",
    ceiling: "Spread is checked before an order is submitted.",
    preference: "A wide spread blocks the send. It is not a plan benefit.",
  },
  {
    name: "ATR stop loss",
    ceiling: "A new order needs a protective stop. The stop is not shrunk to force a trade.",
    preference: "Stops follow the saved policy. This page does not publish a private multiplier.",
  },
  {
    name: "Daily loss protection",
    ceiling: "New entries halt when the effective daily-loss threshold is reached.",
    preference: "Your threshold cannot exceed the platform halt ceiling.",
  },
  {
    name: "Maximum open positions",
    ceiling: "Concurrent positions have a platform ceiling.",
    preference: "Your concurrent-position preference cannot exceed it.",
  },
  {
    name: "Symbol restrictions",
    ceiling: "The autonomous desk trades XAUUSD (gold).",
    preference: "Other symbols are not the public trading universe.",
  },
] as const;

const SECURITY: ReadonlyArray<{ title: string; body: string; icon: LucideIcon }> = [
  {
    title: "Encrypted credentials",
    body: "MT5 worker credentials are sealed before delivery. Passwords are not printed back on screen.",
    icon: KeyRound,
  },
  {
    title: "Secure connections",
    body: "The MT5 gateway talks to the server on the account you connect. A down gateway stays unavailable.",
    icon: ShieldCheck,
  },
  {
    title: "Account isolation",
    body: "A signed-in customer works on their own broker connection. One login does not reveal another customer’s credentials.",
    icon: Unplug,
  },
  {
    title: "Role-based access",
    body: "Customer, admin, and owner routes are separated. Operator controls are not part of this page.",
    icon: FileLock2,
  },
  {
    title: "Worker isolation",
    body: "Authorized MT5 workers receive sealed credentials for the account they are assigned. That path is the implemented worker boundary.",
    icon: Workflow,
  },
  {
    title: "Audit logging",
    body: "Security-relevant actions are written to the audit log. This page does not expose those records.",
    icon: Eye,
  },
  {
    title: "Monitoring and fail-safe",
    body: "Live execution stays behind its enable switch. Risk can refuse an order, and an emergency stop can halt new auto-trading.",
    icon: Shield,
  },
];

const METRICS = [
  "Total trades",
  "Win rate",
  "Net profit",
  "Profit factor",
  "Drawdown",
  "Number of trades",
  "Average trade",
] as const;

const DIFFERENTIATORS: ReadonlyArray<{ title: string; body: string; icon: LucideIcon }> = [
  {
    title: "Capital stays at your broker",
    body: "QuantForg does not custody funds and does not open the brokerage account.",
    icon: Shield,
  },
  {
    title: "Connect the account you have",
    body: "You attach an existing MT5 login. Weltrade is the connection that is verified today.",
    icon: Monitor,
  },
  {
    title: "Analysis and execution are separate",
    body: "Research, a signal, an approved order, and a broker fill are different states.",
    icon: Brain,
  },
  {
    title: "Risk validation before orders",
    body: "The order is checked before submission. A failed check does not reach the broker.",
    icon: ShieldCheck,
  },
  {
    title: "Position monitoring",
    body: "Open positions and protective stops are watched on the connected session.",
    icon: Activity,
  },
  {
    title: "Transparent activity",
    body: "Trading activity is the broker session and its history, not a figure made for this page.",
    icon: BarChart3,
  },
];

const FOOTER = [
  {
    title: "Product",
    links: [
      { href: "/#features", label: "Features" },
      { href: "/#how-it-works", label: "How It Works" },
      { href: "/#strategies", label: "Strategies" },
      { href: "/pricing", label: "Pricing" },
    ],
  },
  {
    title: "Platform",
    links: [
      { href: "/#platform", label: "Platform" },
      { href: "/live", label: "Live Market" },
      { href: "/#brokers", label: "Brokers" },
      { href: "/#security", label: "Security" },
    ],
  },
  {
    title: "Resources",
    links: [
      { href: "/contact", label: "Contact" },
      { href: "mailto:support@quantforg.com", label: "Support" },
      { href: "/#faq", label: "FAQ" },
    ],
  },
  {
    title: "Company",
    links: [
      { href: "/login", label: "Sign In" },
      { href: "/register", label: "Create account" },
      { href: "/contact", label: "Contact" },
    ],
  },
] as const;

function IconBadge({ icon: Icon }: { icon: LucideIcon }) {
  return (
    <span className={styles.icon}>
      <Icon strokeWidth={1.75} aria-hidden />
    </span>
  );
}

export function HomeLanding() {
  return (
    <div className={styles.page}>
      <HomeHeader />
      <main id="main-content" tabIndex={-1}>
        <section id="platform" className={styles.hero}>
          <picture className={styles.heroPicture}>
            <source srcSet="/images/quantforg-hero-background.webp" type="image/webp" />
            <img
              src="/images/quantforg-hero-background.png"
              alt=""
              width={1024}
              height={576}
              className={styles.heroBackground}
              decoding="async"
              fetchPriority="high"
            />
          </picture>
          <div className={`${styles.wrap} ${styles.heroGrid}`}>
            <div className={styles.heroCopy}>
              <p className={styles.kicker}>Institutional trading technology</p>
              <h1 className={styles.headline}>
                <span className={styles.headlineLine}>Trade With Intelligence.</span>
                <span className={`${styles.headlineLine} ${styles.headlineAccent}`}>
                  Execute With Discipline.
                </span>
              </h1>
              <p className={styles.lead}>
                QuantForg connects your MT5 trading account to institutional market intelligence,
                strategy analysis and risk controls — keeping your capital and broker account under
                your control.
              </p>
              <div className={styles.ctaRow}>
                <Link href="/register" className={styles.buttonPrimary}>
                  Connect Your Broker
                </Link>
                <Link href="/#how-it-works" className={styles.buttonSecondary}>
                  Explore How It Works
                </Link>
              </div>
              <ul className={styles.trustList}>
                <li>
                  <Check strokeWidth={1.75} aria-hidden />
                  Your broker account remains yours.
                </li>
                <li>
                  <Check strokeWidth={1.75} aria-hidden />
                  Risk checks before execution.
                </li>
                <li>
                  <Check strokeWidth={1.75} aria-hidden />
                  Transparent and controlled trading.
                </li>
              </ul>
            </div>
          </div>
        </section>

        <div className={styles.mountainRegion}>
          {/* Same Login MountainBackdrop. Sticky + negative margin keeps viewport framing on long pages. */}
          <div className={styles.mountainSticky} aria-hidden>
            <MountainBackdrop intensity="vivid" />
          </div>
          <div className={styles.mountainContent}>

        <section id="brokers" className={styles.section}>
          <div className={styles.wrap}>
            <Reveal>
              <header className={styles.sectionHead}>
                <p className={styles.kicker}>Broker integrations</p>
                <h2>Our Supported Brokers</h2>
                <p className={styles.sectionLead}>
                  Connect through MetaTrader 5 with the brands already listed in QuantForg.
                </p>
              </header>
            </Reveal>
            <ul className={styles.brokerGrid}>
              {BROKERS.map((broker, index) => (
                <li key={broker.name}>
                  <Reveal delayMs={Math.min(index * 40, 280)}>
                    <div className={styles.brokerCard}>
                      <div className={styles.logoWell}>
                        {/* Native img keeps official aspect ratio. Do not recolor. */}
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img src={broker.logoSrc} alt="" />
                      </div>
                      <h3>{broker.name}</h3>
                    </div>
                  </Reveal>
                </li>
              ))}
            </ul>
            <Reveal delayMs={120}>
              <article className={styles.platformBar}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src="/brand/brokers/metatrader5-logo.png" alt="" />
                <div>
                  <p className={styles.kicker}>Trading platform</p>
                  <h3>MetaTrader 5</h3>
                  <p>
                    Orders, positions, and history travel through the MT5 gateway. MetaTrader 5 is
                    not a broker.
                  </p>
                </div>
              </article>
            </Reveal>
          </div>
        </section>

        <section id="features" className={styles.section}>
          <div className={styles.wrap}>
            <Reveal>
              <header className={styles.sectionHead}>
                <p className={styles.kicker}>Platform features</p>
                <h2>What the platform actually does</h2>
                <p className={styles.sectionLead}>
                  Six parts of the same path: connect, analyze, check risk, execute only when
                  authorized, watch the position, and read the broker’s history.
                </p>
              </header>
            </Reveal>
            <div className={styles.featureGrid}>
              {FEATURES.map((item, index) => (
                <Reveal key={item.title} delayMs={Math.min(index * 50, 250)}>
                  <article className={`${styles.card} ${styles.featureCard}`}>
                    <IconBadge icon={item.icon} />
                    <div className={styles.featureCopy}>
                      <h3>{item.title}</h3>
                      <p>{item.body}</p>
                    </div>
                  </article>
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        <section id="how-it-works" className={styles.section}>
          <div className={styles.wrap}>
            <Reveal>
              <header className={styles.sectionHead}>
                <p className={styles.kicker}>How it works</p>
                <h2>Three steps to a connected account</h2>
                <p className={styles.sectionLead}>
                  You create a QuantForg account and connect a broker login you already have.
                  QuantForg does not open that brokerage account for you.
                </p>
              </header>
            </Reveal>
            <ol className={styles.stepGrid}>
              {STEPS.map((step, index) => (
                <li key={step.n}>
                  <Reveal delayMs={Math.min(index * 60, 180)}>
                    <div className={styles.step}>
                      <span className={styles.stepIndex}>{step.n}</span>
                      <h3>{step.title}</h3>
                      <p>{step.body}</p>
                      <Link href={step.href} className={styles.textLink}>
                        {step.label}
                      </Link>
                    </div>
                  </Reveal>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section id="workflow" className={styles.section}>
          <div className={styles.wrap}>
            <Reveal>
              <header className={styles.sectionHead}>
                <p className={styles.kicker}>Trading workflow</p>
                <h2>Eight stages, in the order the desk runs</h2>
                <p className={styles.sectionLead}>
                  Scanning and analysis happen before any order. Risk validation sits in front of
                  execution. Performance is the broker’s record after the fact.
                </p>
              </header>
            </Reveal>
            <ol className={styles.flowGrid}>
              {WORKFLOW.map((step, index) => (
                <li key={step.title}>
                  <Reveal delayMs={Math.min(index * 35, 245)}>
                    <div className={styles.flowCard}>
                      <span className={styles.flowIndex}>{String(index + 1).padStart(2, "0")}</span>
                      <h3>{step.title}</h3>
                      <p>{step.body}</p>
                    </div>
                  </Reveal>
                </li>
              ))}
            </ol>
            <Reveal>
              <div className={styles.rulePanel}>
                {RULES.map((rule) => (
                  <p key={rule}>{rule}</p>
                ))}
              </div>
            </Reveal>
          </div>
        </section>

        <section id="strategies" className={styles.section}>
          <div className={styles.wrap}>
            <Reveal>
              <header className={styles.sectionHead}>
                <p className={styles.kicker}>Strategy intelligence</p>
                <h2>Profiles that exist in the registry</h2>
                <p className={styles.sectionLead}>
                  Five scalping profiles can be selected for an order, and only after the risk and
                  execution gates. The other names are factors or advisory votes. Listing one here
                  does not mean it is placing trades.
                </p>
              </header>
            </Reveal>
            <p className={styles.groupLabel}>Execution profiles</p>
            <ul className={`${styles.strategyGrid} ${styles.execGrid}`}>
              {EXECUTION_PROFILES.map((item) => (
                <li key={item.title} className={styles.strategyCard}>
                  <IconBadge icon={item.icon} />
                  <span className={`${styles.status} ${styles.statusExec}`}>{item.status}</span>
                  <h3>{item.title}</h3>
                  <p>{item.body}</p>
                </li>
              ))}
            </ul>
            <p className={styles.groupLabel}>Factors and advisory votes</p>
            <ul className={styles.strategyGrid}>
              {ANALYSIS_FACTORS.map((item) => (
                <li key={item.title} className={styles.strategyCard}>
                  <IconBadge icon={item.icon} />
                  <span className={`${styles.status} ${styles.statusNeutral}`}>{item.status}</span>
                  <h3>{item.title}</h3>
                  <p>{item.body}</p>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section id="risk" className={styles.section}>
          <div className={styles.wrap}>
            <header className={styles.sectionHead}>
              <p className={styles.kicker}>Risk and capital protection</p>
              <h2>Ceilings and preferences are not the same thing</h2>
              <p className={styles.sectionLead}>
                Platform hard limits are ceilings. A customer preference can be tighter. It cannot
                loosen a ceiling, and a subscription plan cannot bypass the check. Private account
                settings are not published on this page.
              </p>
            </header>
            <p className={styles.riskIntro}>
              Grid, martingale, and averaging-down remain disabled. A planned limit is not a cap
              on a realised loss if the market gaps.
            </p>
            <div className={styles.riskHead} aria-hidden>
              <span>Control</span>
              <span>Platform ceiling</span>
              <span>Customer preference</span>
            </div>
            <div>
              {RISK_ROWS.map((row) => (
                <div key={row.name} className={styles.riskRow}>
                  <strong>{row.name}</strong>
                  <span>{row.ceiling}</span>
                  <span>{row.preference}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="security" className={styles.section}>
          <div className={styles.wrap}>
            <Reveal>
              <header className={styles.sectionHead}>
                <p className={styles.kicker}>Security and reliability</p>
                <h2>Controls that are actually in the product</h2>
                <p className={styles.sectionLead}>
                  Sign-in, broker credentials, and order permission stay on the systems that already
                  exist. No certification, license, or regulatory approval is claimed here.
                </p>
              </header>
            </Reveal>
            <div className={styles.securityGrid}>
              {SECURITY.map((item) => (
                <article key={item.title} className={styles.securityCard}>
                  <IconBadge icon={item.icon} />
                  <h3>{item.title}</h3>
                  <p>{item.body}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="performance" className={styles.section}>
          <div className={styles.wrap}>
            <header className={styles.sectionHead}>
              <p className={styles.kicker}>Performance and transparency</p>
              <h2>Figures appear only after a connection</h2>
              <p className={styles.sectionLead}>
                Win rate, profit, and drawdown are calculated from broker deals once a session
                returns history. Until then every value on this page stays blank.
              </p>
            </header>
            <ul className={styles.metricGrid}>
              {METRICS.map((label) => (
                <li key={label} className={styles.metricCard}>
                  <p>{label}</p>
                  <strong>—</strong>
                  <span>Available from your broker history, not from this page.</span>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section id="difference" className={styles.section}>
          <div className={styles.wrap}>
            <header className={styles.sectionHead}>
              <p className={styles.kicker}>Why QuantForg is different</p>
              <h2>Built around the account you connect</h2>
              <p className={styles.sectionLead}>
                The product is the path from a broker login you control to a checked order and a
                record you can read back.
              </p>
            </header>
            <div className={styles.whyGrid}>
              {DIFFERENTIATORS.map((item) => (
                <article key={item.title} className={styles.whyCard}>
                  <IconBadge icon={item.icon} />
                  <h3>{item.title}</h3>
                  <p>{item.body}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="pricing" className={styles.section}>
          <div className={styles.wrap}>
            <Reveal>
              <header className={styles.sectionHead}>
                <p className={styles.kicker}>Pricing</p>
                <h2>Software access, monthly</h2>
                <p className={styles.sectionLead}>
                  Starter, Professional, and Premium are the production plans. A plan grants software
                  access. It does not grant trading profits, and it does not bypass risk checks.
                </p>
              </header>
            </Reveal>
            <div className={styles.priceGrid}>
              {BILLING_PLANS.map((plan) => (
                <article
                  key={plan.id}
                  className={`${styles.priceCard} ${plan.highlighted ? styles.priceFeatured : ""}`}
                >
                  <div className={styles.priceFlagSlot}>
                    {plan.highlighted ? <span className={styles.priceFlag}>Most popular</span> : null}
                  </div>
                  <h3>{plan.name}</h3>
                  <p>{plan.positioning}</p>
                  <p className={styles.priceAmount}>
                    <strong>{formatUsd(plan.monthlyPriceUsd)}</strong>
                    <span>/ month</span>
                  </p>
                  <p className={styles.priceMeta}>Paid via {BILLING_PROVIDER.paymentMethodLabel}</p>
                  <ul className={styles.entitlements}>
                    {plan.entitlements.map((item) => (
                      <li key={item}>
                        <Check strokeWidth={1.75} aria-hidden />
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                  <Link
                    href={`/billing/checkout?plan=${plan.id}`}
                    className={plan.highlighted ? styles.buttonPrimary : styles.buttonSecondary}
                  >
                    {plan.ctaLabel}
                  </Link>
                  <Link href={`/register?plan=${plan.id}`} className={styles.textLink}>
                    Create account first, then checkout
                  </Link>
                </article>
              ))}
            </div>
            <div className={styles.billingNote}>
              <p>{TRIAL_POSITIONING}</p>
              <p>
                The trial is {TRIAL_DAYS} days of Starter access. It does not auto-convert to a
                paid plan.
              </p>
              <p>{BILLING_PROVIDER.note}</p>
              {ANNUAL_BILLING_SUPPORTED ? null : (
                <p>Monthly price shown. Annual billing is not offered.</p>
              )}
              <p>
                <Link href="/pricing" className={styles.textLink}>
                  Compare plans on the pricing page
                </Link>
              </p>
            </div>
          </div>
        </section>

        <section id="faq" className={styles.section}>
          <div className={styles.wrap}>
            <header className={styles.sectionHead}>
              <p className={styles.kicker}>FAQ</p>
              <h2>Questions about the product</h2>
              <p className={styles.sectionLead}>
                Short answers from the way the account, broker connection, and risk checks work
                today.
              </p>
            </header>
            <div className={styles.faq}>
              <FaqList />
            </div>
          </div>
        </section>

        <section className={`${styles.section} ${styles.cta}`}>
          <div className={styles.wrap}>
            <div className={styles.ctaPanel}>
              <p className={styles.kicker}>Get started</p>
              <h2>Ready to Trade With More Intelligence?</h2>
              <p>Create your account, choose your plan and connect your broker to get started.</p>
              <div className={styles.ctaRow}>
                <Link href="/register" className={styles.buttonPrimary}>
                  Connect Your Broker
                </Link>
                <Link href="/pricing" className={styles.buttonSecondary}>
                  View Pricing
                </Link>
              </div>
            </div>
          </div>
        </section>

          <footer className={styles.footer}>
            <div className={`${styles.wrap} ${styles.footerGrid}`}>
              <div className={styles.footerBrand}>
                <BrandLogo size={32} caption={false} />
                <p>
                  QuantForg is institutional trading technology sold by subscription. Connect your own
                  MetaTrader 5 broker account where supported. Software access is not a promise of
                  trading profits.
                </p>
              </div>
              <div className={styles.footerCols}>
                {FOOTER.map((column) => (
                  <div key={column.title}>
                    <p>{column.title}</p>
                    <ul>
                      {column.links.map((link) => (
                        <li key={link.label}>
                          {link.href.startsWith("/") ? (
                            <Link href={link.href}>{link.label}</Link>
                          ) : (
                            <a href={link.href}>{link.label}</a>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
                <div>
                  <p>Legal</p>
                  <ul>
                    <li>
                      <Link href="/privacy">Privacy</Link>
                    </li>
                    <li>
                      <Link href="/terms">Terms</Link>
                    </li>
                    <li>
                      <Link href="/risk-disclosure">Risk Disclosure</Link>
                    </li>
                  </ul>
                </div>
              </div>
            </div>
            <div className={styles.wrap}>
              <p className={styles.legalLine}>
                © 2026 QuantForg. Trading can lose capital. This site does not promise profits.
              </p>
            </div>
          </footer>
          </div>
        </div>
      </main>
    </div>
  );
}
