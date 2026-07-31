/**
 * CSS-only QuantForg product previews — no stock art, no fabricated metrics.
 * Visual chrome only; not live desk data.
 */

const PREVIEWS = [
  {
    title: "Dashboard",
    caption: "Institutional overview",
    accent: "Equity · Exposure · Status",
    bars: [42, 58, 35, 71, 48, 63, 40, 77, 52, 66],
  },
  {
    title: "AI Decision Engine",
    caption: "Context before capital",
    accent: "Validate · Regime · Gate",
    bars: [55, 48, 62, 44, 70, 38, 66, 51, 73, 47],
  },
  {
    title: "Live Trading",
    caption: "MT5-connected desk",
    accent: "Positions · Orders · Sync",
    bars: [38, 65, 52, 78, 41, 69, 55, 72, 46, 60],
  },
  {
    title: "Portfolio Risk",
    caption: "Book-level controls",
    accent: "Sizing · Caps · Drawdown",
    bars: [60, 45, 68, 40, 74, 50, 58, 71, 43, 64],
  },
  {
    title: "Analytics",
    caption: "Performance clarity",
    accent: "PnL · Expectancy · Edge",
    bars: [48, 70, 42, 66, 55, 78, 36, 62, 50, 72],
  },
  {
    title: "Trade History",
    caption: "Session memory",
    accent: "Journal · Fills · Notes",
    bars: [52, 40, 65, 48, 72, 44, 68, 55, 60, 46],
  },
  {
    title: "Performance",
    caption: "Live metrics",
    accent: "Equity curve · Risk",
    bars: [35, 48, 58, 45, 70, 62, 75, 50, 68, 55],
  },
  {
    title: "AI Validation",
    caption: "Pre-trade checks",
    accent: "Policy · Quality · Confidence",
    bars: [64, 52, 70, 45, 58, 72, 40, 66, 54, 61],
  },
] as const;

export function ProductPreviews() {
  return (
    <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {PREVIEWS.map((p) => (
        <li key={p.title} className="qf-glass-card qf-glass-card--hover overflow-hidden p-0">
          <div className="qf-browser-chrome border-b border-[var(--border)] bg-[var(--bg-elevated)]/90 px-3 py-2">
            <div className="flex items-center gap-1.5" aria-hidden>
              <span className="h-2 w-2 rounded-full bg-[var(--border-strong)]" />
              <span className="h-2 w-2 rounded-full bg-[var(--border-strong)]" />
              <span className="h-2 w-2 rounded-full bg-[var(--border-strong)]" />
            </div>
            <p className="mt-1.5 truncate rounded-md bg-[var(--surface)] px-2 py-1 font-mono text-[10px] text-[var(--fg-subtle)]">
              quantforg · {p.title.toLowerCase()}
            </p>
          </div>
          <div className="relative bg-[var(--bg)]/60 px-3 pb-3 pt-3">
            <div className="mb-2 flex items-center justify-between gap-2">
              <div>
                <p className="text-xs font-semibold text-[var(--fg)]">{p.title}</p>
                <p className="text-[10px] text-[var(--fg-subtle)]">{p.caption}</p>
              </div>
              <span className="rounded-full border border-[var(--accent)]/30 bg-[var(--accent-soft)] px-2 py-0.5 text-[9px] font-medium uppercase tracking-wider text-[var(--accent)]">
                Live
              </span>
            </div>
            <div
              className="flex h-20 items-end gap-1"
              role="img"
              aria-label={`${p.title} abstract preview — ${p.accent}`}
            >
              {p.bars.map((h, i) => (
                <span
                  key={i}
                  className="flex-1 rounded-sm bg-[var(--accent)]/25"
                  style={{ height: `${h}%` }}
                />
              ))}
            </div>
            <p className="mt-2 text-[10px] tracking-wide text-[var(--fg-subtle)]">{p.accent}</p>
            <ul className="mt-2 space-y-1" aria-hidden>
              <li className="h-1.5 w-full rounded bg-[var(--surface-2)]" />
              <li className="h-1.5 w-[80%] rounded bg-[var(--surface-2)]" />
              <li className="h-1.5 w-[60%] rounded bg-[var(--surface-2)]" />
            </ul>
          </div>
        </li>
      ))}
    </ul>
  );
}
