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
import { SiteFooter } from "@/components/marketing/site-footer";
import { MountainBackdrop } from "@/components/brand/mountain-backdrop";
import {
  ANNUAL_BILLING_SUPPORTED,
  BILLING_PLANS,
  BILLING_PROVIDER,
  formatUsd,
} from "@/lib/billing/plans";
import styles from "./home-landing.module.css";

const FEATURES: ReadonlyArray<{ title: string; body: string; icon: LucideIcon }> = [
  {
    title: "QuantForg AI Assistant",
    body: "Ask anything about gold and trading, in your own language. QuantForg AI explains the live market, trend, key support and resistance, and the news that can move price.",
    icon: Brain,
  },
  {
    title: "Chart Screenshot Analysis",
    body: "Upload or paste a screenshot of any chart. QuantForg AI reads the structure, levels and indicators that are visible, compares it with the live price and lays out the bullish and bearish scenarios.",
    icon: BarChart3,
  },
  {
    title: "Automated Gold Trading",
    body: "The QuantForg Robot watches XAUUSD on every trading day and only trades when its conditions and your risk limits allow. Quiet markets mean no trade, not a forced one.",
    icon: Send,
  },
  {
    title: "Risk Protection",
    body: "Every trade carries a stop loss. Your risk per trade, daily loss limit and position limits are checked before any order reaches your broker.",
    icon: Shield,
  },
  {
    title: "Your MT5, Your Broker",
    body: "Connect the MetaTrader 5 account you already own at a supported broker. Your money stays at your broker; QuantForg never holds funds.",
    icon: Monitor,
  },
  {
    title: "Live Monitoring & Real Results",
    body: "See balance, equity, open positions and robot status live. Performance comes from your broker's own trade history, never from sample numbers.",
    icon: Activity,
  },
];

const STEPS = [
  {
    n: "01",
    title: "Create Your Account",
    body: "Sign up with your email and password and confirm your email. It takes about a minute.",
    href: "/register",
    label: "Create account",
  },
  {
    n: "02",
    title: "Connect Your Broker",
    body: "Open Broker Accounts, choose your broker and enter your MT5 login. QuantForg checks it within seconds and shows Connected or Rejected.",
    href: "/brokers",
    label: "Open Broker Accounts",
  },
  {
    n: "03",
    title: "Verify & Activate",
    body: "Set your risk limits, choose a plan and start the robot. Nothing trades until you start it, and you can pause or stop it at any time.",
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
  { title: "Market Scanning", body: "Watches the live gold market on several timeframes." },
  { title: "AI Analysis", body: "Reads trend, structure, momentum and market conditions." },
  { title: "Strategy Evaluation", body: "Checks whether a high-quality setup is really there." },
  { title: "Risk Validation", body: "Applies your risk limits; a failed check means no trade." },
  { title: "Order Execution", body: "Places the trade on your MT5 account with a stop loss." },
  { title: "Trade Management", body: "Watches open positions and protects profits." },
  { title: "Trade Closure", body: "Closes at the target, the stop, or when conditions change." },
  { title: "Performance Review", body: "Reports results straight from your broker's history." },
];

const RULES = [
  "Analysis is not an order.",
  "A signal is not an executed trade.",
  "Risk validation happens before order submission.",
  "The robot trades only when you start it and your broker is connected.",
] as const;

const EXECUTION_PROFILES: ReadonlyArray<{
  title: string;
  status: string;
  body: string;
  icon: LucideIcon;
}> = [
  {
    title: "Trend Following",
    status: "Setup",
    body: "Joins an established trend after a pullback, in the direction the market is already moving.",
    icon: MoveUpRight,
  },
  {
    title: "Breakout",
    status: "Setup",
    body: "Trades a decisive move out of a range when momentum confirms it.",
    icon: Zap,
  },
  {
    title: "Mean Reversion",
    status: "Setup",
    body: "In a ranging market, looks for price returning from an extreme toward fair value.",
    icon: RefreshCcw,
  },
  {
    title: "Momentum",
    status: "Setup",
    body: "Follows strong, confirmed momentum while it lasts.",
    icon: Gauge,
  },
  {
    title: "SMC Scalping",
    status: "Setup",
    body: "Smart-money price action: how institutions leave footprints in liquidity and structure.",
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
    status: "Market factor",
    body: "Spots stop-hunts above highs or below lows before a reversal.",
    icon: Waves,
  },
  {
    title: "Order Block",
    status: "Market factor",
    body: "Zones where large orders previously moved price.",
    icon: Layers,
  },
  {
    title: "Fair Value Gap",
    status: "Market factor",
    body: "Price imbalances that the market often comes back to fill.",
    icon: Target,
  },
  {
    title: "RSI",
    status: "Market factor",
    body: "Measures momentum and overbought or oversold conditions.",
    icon: Activity,
  },
  {
    title: "MACD",
    status: "Market factor",
    body: "Confirms trend strength and momentum shifts.",
    icon: LineChart,
  },
  {
    title: "Bollinger Bands",
    status: "Market factor",
    body: "Reads volatility so trades fit current market conditions.",
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
    body: "Your MT5 password is encrypted and never shown again, to anyone.",
    icon: KeyRound,
  },
  {
    title: "Secure connections",
    body: "All traffic between you, QuantForg and your broker is encrypted.",
    icon: ShieldCheck,
  },
  {
    title: "Account isolation",
    body: "Every customer's account and broker connection is kept separate from every other customer's.",
    icon: Unplug,
  },
  {
    title: "Role-based access",
    body: "Customers and administrators have separate, permission-checked access.",
    icon: FileLock2,
  },
  {
    title: "Worker isolation",
    body: "Each connected account trades in its own isolated environment.",
    icon: Workflow,
  },
  {
    title: "Audit logging",
    body: "Important account and admin actions are recorded so they can always be reviewed.",
    icon: Eye,
  },
  {
    title: "Monitoring and fail-safe",
    body: "Continuous monitoring with automatic safety stops: if something looks wrong, the robot stops opening trades.",
    icon: Shield,
  },
];

const DIFFERENTIATORS: ReadonlyArray<{ title: string; body: string; icon: LucideIcon }> = [
  {
    title: "Capital stays at your broker",
    body: "QuantForg does not custody funds and does not open the brokerage account.",
    icon: Shield,
  },
  {
    title: "Connect the account you have",
    body: "Use your existing MT5 account at any supported broker. No new brokerage account needed.",
    icon: Monitor,
  },
  {
    title: "Analysis and execution are separate",
    body: "QuantForg AI explains and analyzes; only the robot trades, and only within your limits.",
    icon: Brain,
  },
  {
    title: "Risk validation before orders",
    body: "Every order is checked against your risk limits first. A failed check means no trade.",
    icon: ShieldCheck,
  },
  {
    title: "Position monitoring",
    body: "Open positions and their stop losses are watched continuously.",
    icon: Activity,
  },
  {
    title: "Transparent activity",
    body: "Your results come straight from your broker's history. No sample or simulated numbers.",
    icon: BarChart3,
  },
];

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
              <p className={styles.kicker}>Institutional AI Trading Command Center</p>
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
                    The robot trades on your MetaTrader 5 account. MetaTrader 5 is the trading
                    platform; your broker holds the account.
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
                  An AI assistant that analyzes the market and your charts, and a gold trading robot
                  that trades within the risk limits you set.
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
                <h2>What the robot looks for</h2>
                <p className={styles.sectionLead}>
                  The QuantForg Robot combines several proven ways of reading the gold market. It
                  trades only when the setup is strong and your risk limits allow it.
                </p>
              </header>
            </Reveal>
            <p className={styles.groupLabel}>Trading setups</p>
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
            <p className={styles.groupLabel}>What it reads in the market</p>
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
                  Choose Starter, Professional or Premium. Every plan includes QuantForg AI and the
                  robot. A plan is software access: it does not guarantee profits or bypass your risk limits.
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
              <p>
                Create your account, connect and verify your MT5 broker for free. The robot
                starts trading only on an active subscription.
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

          <SiteFooter />
          </div>
        </div>
      </main>
    </div>
  );
}
