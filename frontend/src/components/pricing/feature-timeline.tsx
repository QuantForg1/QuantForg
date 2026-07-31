import {
  BarChart3,
  Brain,
  Gauge,
  Radar,
  Shield,
  Zap,
} from "lucide-react";

const STEPS = [
  {
    title: "Market Analysis",
    body: "Multi-timeframe structure, liquidity, and smart money context — continuously observed.",
    icon: Radar,
  },
  {
    title: "AI Decision",
    body: "Institutional decision intelligence evaluates regime, quality, and confidence before action.",
    icon: Brain,
  },
  {
    title: "Risk Calculation",
    body: "Dynamic sizing and portfolio constraints compute exposure before capital is committed.",
    icon: Shield,
  },
  {
    title: "Execution",
    body: "Gated MT5 live paths — automation under operator control, not opaque black boxes.",
    icon: Zap,
  },
  {
    title: "Trade Management",
    body: "Trailing, break-even, partials, and pyramiding as institutional trade controls.",
    icon: Gauge,
  },
  {
    title: "Performance Analytics",
    body: "Journal, equity clarity, and live metrics close the loop for the next decision.",
    icon: BarChart3,
  },
] as const;

export function FeatureTimeline() {
  return (
    <ol className="relative mx-auto max-w-3xl space-y-0">
      {STEPS.map((step, i) => {
        const Icon = step.icon;
        const last = i === STEPS.length - 1;
        return (
          <li key={step.title} className="relative flex gap-4 pb-8 last:pb-0 sm:gap-5">
            {!last ? (
              <span
                className="absolute left-[1.15rem] top-10 bottom-0 w-px bg-[linear-gradient(180deg,var(--accent),transparent)] sm:left-[1.35rem]"
                aria-hidden
              />
            ) : null}
            <span className="relative z-[1] flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-[var(--accent)]/35 bg-[var(--accent-soft)] text-[var(--accent)] sm:h-11 sm:w-11">
              <Icon className="h-4 w-4 sm:h-5 sm:w-5" strokeWidth={1.75} aria-hidden />
            </span>
            <div className="qf-glass-card min-w-0 flex-1 p-4 sm:p-5">
              <p className="text-[10px] font-medium uppercase tracking-[0.14em] text-[var(--accent)]">
                Step {i + 1}
              </p>
              <h3 className="mt-1 text-base font-semibold tracking-tight text-[var(--fg)]">
                {step.title}
              </h3>
              <p className="mt-1.5 text-sm leading-relaxed text-[var(--fg-muted)]">{step.body}</p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
