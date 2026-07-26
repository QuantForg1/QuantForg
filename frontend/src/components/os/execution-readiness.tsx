"use client";

/**
 * Trading status — independent lines from live session signals.
 * Never invents readiness; never shows contradictory Trading Enabled.
 */

import { cn } from "@/lib/utils";
import type { TradingStatusLine } from "@/lib/trading/status-lines";

export function ExecutionReadiness({
  lines,
  className,
}: {
  lines: TradingStatusLine[];
  className?: string;
}) {
  if (!lines.length) {
    return (
      <div
        className={cn(
          "rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-4 text-center",
          className,
        )}
      >
        <p className="qf-heading text-[var(--fg)]">Trading status</p>
        <p className="qf-caption mt-1">
          Open a ticket with a live session to evaluate status.
        </p>
      </div>
    );
  }

  return (
    <section
      className={cn(
        "rounded-md border border-[var(--border)] bg-[var(--surface)] p-3",
        className,
      )}
      aria-label="Trading status"
    >
      <header className="mb-2">
        <h2 className="qf-label text-[var(--fg)]">Trading status</h2>
      </header>
      <ul className="space-y-1.5">
        {lines.map((line) => (
          <li
            key={line.id}
            className="flex items-center justify-between gap-3 text-[var(--text-caption)]"
          >
            <span className="text-[var(--fg-muted)]">{line.label}</span>
            <span
              className={cn(
                "inline-flex shrink-0 items-center gap-1.5 tabular",
                line.tone === "ok" && "text-[var(--success)]",
                line.tone === "warn" && "text-[var(--warning)]",
                line.tone === "off" && "text-[var(--danger)]",
                line.tone === "unknown" && "text-[var(--fg-subtle)]",
              )}
            >
              <span
                className="qf-status-dot h-1.5 w-1.5 rounded-full bg-current"
                aria-hidden
              />
              {line.value}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
