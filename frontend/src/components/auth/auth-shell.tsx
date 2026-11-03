import Link from "next/link";
import { BarChart3, Brain, Globe, Shield, Zap } from "lucide-react";
import { BrandLogo } from "@/components/brand/brand-logo";
import { MountainBackdrop } from "@/components/brand/mountain-backdrop";

const POINTS = [
  {
    title: "Real Market Analysis",
    body: "Research on the connected gold feed. A chart is not a filled order.",
    icon: BarChart3,
    tone: "bg-[var(--accent)]",
  },
  {
    title: "Automated Execution",
    body: "From signal to broker only after the existing risk gates pass.",
    icon: Brain,
    tone: "bg-[#7c5cff]",
  },
  {
    title: "Advanced Risk Management",
    body: "Saved limits can block an order before it is sent.",
    icon: Shield,
    tone: "bg-[var(--hot)]",
  },
  {
    title: "24/5 Trading",
    body: "Active Monday to Friday. The weekend is not marked as a live session.",
    icon: Zap,
    tone: "bg-[var(--success)]",
  },
] as const;

const TRUST = [
  ["Secure & Encrypted", "Email and password use the existing account service."],
  ["Works with MT5 Brokers", "Connect the Weltrade account you already own."],
  ["Fully Automated", "Execution stays under the saved risk settings."],
  ["Institutional Grade", "One workspace for analysis, risk, and positions."],
] as const;

export function AuthShell({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden bg-[var(--bg)]">
      <MountainBackdrop withCandles />
      <header className="relative z-10 flex items-center justify-between px-4 py-5 sm:px-8">
        <Link href="/">
          <BrandLogo size={36} caption="Institutional Trading Intelligence" priority />
        </Link>
        <span
          className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/5 px-3 py-1.5 text-xs font-medium text-[var(--fg-muted)] backdrop-blur-sm"
          title="Language selection is not available yet"
        >
          <Globe className="h-3.5 w-3.5" aria-hidden />
          English
        </span>
      </header>
      <main
        id="main-content"
        className="relative z-10 mx-auto grid w-full max-w-6xl flex-1 items-center gap-10 px-4 pb-8 sm:px-8 lg:grid-cols-[1fr_minmax(0,440px)]"
        tabIndex={-1}
      >
        <section className="max-w-xl">
          <h2 className="font-[family-name:var(--font-display)] text-4xl leading-[1.05] tracking-tight sm:text-5xl">
            Trade Smarter with{" "}
            <span className="text-[var(--hot)]">Institutional Intelligence.</span>
          </h2>
          <p className="mt-4 text-base leading-relaxed text-[var(--fg-muted)]">
            Connect your broker, let QuantForg analyze markets, manage risk, and execute
            trades under your approved settings.
          </p>
          <ul className="mt-8 space-y-4">
            {POINTS.map((point) => {
              const Icon = point.icon;
              return (
                <li key={point.title} className="flex gap-3">
                  <span
                    className={`mt-0.5 inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-white shadow-[0_8px_20px_rgba(2,8,24,0.35)] ${point.tone}`}
                  >
                    <Icon className="h-5 w-5" aria-hidden />
                  </span>
                  <span>
                    <span className="block font-semibold">{point.title}</span>
                    <span className="mt-0.5 block text-sm text-[var(--fg-muted)]">{point.body}</span>
                  </span>
                </li>
              );
            })}
          </ul>
        </section>
        <section className="qf-auth-card rounded-[1.25rem] border border-[color-mix(in_srgb,var(--accent)_45%,var(--border))] bg-[color-mix(in_srgb,var(--surface)_88%,#061a38)] p-6 shadow-[var(--shadow-elevated),0_0_0_1px_rgba(22,139,255,0.18),0_0_48px_rgba(22,139,255,0.12)] backdrop-blur-md sm:p-8">
          <div className="mb-6 flex flex-col items-center text-center">
            <BrandLogo size={42} caption="Institutional Trading Intelligence" />
            <h1 className="mt-5 text-3xl font-semibold tracking-tight">{title}</h1>
            <p className="mt-2 text-sm leading-relaxed text-[var(--fg-muted)]">{subtitle}</p>
          </div>
          {children}
        </section>
      </main>
      <footer className="relative z-10 border-t border-[var(--border)] bg-[var(--bg-elevated)]/80 backdrop-blur-sm">
        <ul className="mx-auto grid w-full max-w-6xl gap-4 px-4 py-5 sm:grid-cols-2 sm:px-8 lg:grid-cols-4">
          {TRUST.map(([titleText, body]) => (
            <li key={titleText} className="flex gap-3">
              <span className="mt-0.5 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[var(--accent-soft)] text-[var(--accent)]">
                <Shield className="h-4 w-4" aria-hidden />
              </span>
              <span>
                <p className="text-sm font-semibold">{titleText}</p>
                <p className="mt-1 text-xs leading-relaxed text-[var(--fg-muted)]">{body}</p>
              </span>
            </li>
          ))}
        </ul>
      </footer>
    </div>
  );
}
