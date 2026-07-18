"use client";

import { memo, useMemo } from "react";
import { Scale } from "lucide-react";
import { Button } from "@/components/ui/button";
import { asList, asRecord, num, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

type CounselLine = {
  id: string;
  text: string;
  tone: "ok" | "warn" | "block" | "neutral";
};

/**
 * Portfolio Counsel — always-on advisory layer for the book.
 * Grounded in live metrics + portfolio intelligence. Never invents balances.
 */
export const PortfolioCounsel = memo(function PortfolioCounsel({
  connected,
  equity,
  freeMargin,
  marginLevel,
  floating,
  positionCount,
  intelligence,
  collapsed,
  onToggle,
  className,
}: {
  connected: boolean;
  equity: number;
  freeMargin: number;
  marginLevel: number;
  floating: number;
  positionCount: number;
  intelligence: Record<string, unknown> | null;
  collapsed: boolean;
  onToggle: () => void;
  className?: string;
}) {
  const lines = useMemo((): CounselLine[] => {
    const next: CounselLine[] = [];

    if (!connected) {
      next.push({
        id: "offline",
        text: "Attach a live session to counsel the book.",
        tone: "block",
      });
      return next;
    }

    next.push({
      id: "session",
      text:
        positionCount === 0
          ? "Book is flat — no open risk."
          : `${positionCount} open position${positionCount === 1 ? "" : "s"} on the book.`,
      tone: "ok",
    });

    if (Number.isFinite(freeMargin) && freeMargin <= 0) {
      next.push({
        id: "free",
        text: "Free margin exhausted — reduce size or close risk before adding.",
        tone: "block",
      });
    }

    if (Number.isFinite(marginLevel) && marginLevel > 0 && marginLevel < 100) {
      next.push({
        id: "ml",
        text: `Margin level ${marginLevel.toFixed(0)}% — intervention territory.`,
        tone: "block",
      });
    } else if (Number.isFinite(marginLevel) && marginLevel > 0 && marginLevel < 200) {
      next.push({
        id: "ml-warn",
        text: `Margin level ${marginLevel.toFixed(0)}% — elevated leverage pressure.`,
        tone: "warn",
      });
    }

    if (
      Number.isFinite(floating) &&
      Number.isFinite(equity) &&
      equity > 0 &&
      floating < 0 &&
      Math.abs(floating) / equity > 0.05
    ) {
      next.push({
        id: "float",
        text: "Floating loss exceeds 5% of equity — review largest positions.",
        tone: "warn",
      });
    }

    if (intelligence) {
      if (intelligence.portfolio_available === false) {
        next.push({
          id: "pi",
          text: str(
            intelligence.portfolio_unavailable_reason,
            "Portfolio intelligence sync unavailable.",
          ),
          tone: "neutral",
        });
      } else {
        const risk = asRecord(intelligence.risk);
        const metrics = asRecord(risk.metrics);
        if (str(metrics.portfolio_var_status) !== "unavailable") {
          const v = num(metrics.portfolio_var);
          if (Number.isFinite(v)) {
            next.push({
              id: "var",
              text: `VaR 95% ≈ ${v.toFixed(2)} (historical deal PnL).`,
              tone: "neutral",
            });
          }
        }
        const recs = asList(
          asRecord(intelligence.optimizer).recommendations,
        ).map(asRecord);
        const first = recs[0];
        if (first) {
          next.push({
            id: "opt",
            text: str(
              first.rationale ?? first.message ?? first.action,
              `${str(first.symbol)} allocation suggestion`,
            ).slice(0, 140),
            tone: "warn",
          });
        }
      }
    }

    return next.slice(0, 5);
  }, [
    connected,
    equity,
    freeMargin,
    marginLevel,
    floating,
    positionCount,
    intelligence,
  ]);

  const blocked = lines.some((l) => l.tone === "block");
  const warned = lines.some((l) => l.tone === "warn");

  if (collapsed) {
    return (
      <div
        className={cn(
          "flex h-8 shrink-0 items-center justify-between border-b border-[var(--border)] bg-[var(--surface)] px-3",
          className,
        )}
      >
        <div className="flex items-center gap-2">
          <Scale className="h-3.5 w-3.5 text-[var(--fg-subtle)]" aria-hidden />
          <span className="qf-caption">
            Portfolio Counsel{" "}
            <span
              className={cn(
                "tabular",
                blocked && "text-[var(--danger)]",
                !blocked && warned && "text-[var(--warning)]",
                !blocked && !warned && "text-[var(--success)]",
              )}
            >
              {blocked ? "intervene" : warned ? "caution" : "clear"}
            </span>
          </span>
        </div>
        <Button size="sm" variant="ghost" className="h-6 px-2 text-[10px]" onClick={onToggle}>
          Expand
        </Button>
      </div>
    );
  }

  return (
    <section
      className={cn(
        "shrink-0 border-b border-[var(--border)] bg-[var(--surface)] px-3 py-2",
        className,
      )}
      aria-label="Portfolio Counsel"
    >
      <header className="mb-1.5 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Scale className="h-3.5 w-3.5 text-[var(--accent)]" aria-hidden />
          <h2 className="qf-label text-[var(--fg)]">Portfolio Counsel</h2>
          <span
            className={cn(
              "qf-caption tabular",
              blocked && "text-[var(--danger)]",
              !blocked && warned && "text-[var(--warning)]",
              !blocked && !warned && "text-[var(--success)]",
            )}
          >
            {blocked ? "Intervention" : warned ? "Caution" : "Ready"}
          </span>
        </div>
        <Button size="sm" variant="ghost" className="h-6 px-2 text-[10px]" onClick={onToggle}>
          Collapse
        </Button>
      </header>
      <ul className="flex flex-wrap gap-x-4 gap-y-1">
        {lines.map((l) => (
          <li
            key={l.id}
            className={cn(
              "text-[11px] leading-snug",
              l.tone === "ok" && "text-[var(--success)]",
              l.tone === "warn" && "text-[var(--warning)]",
              l.tone === "block" && "text-[var(--danger)]",
              l.tone === "neutral" && "text-[var(--fg-muted)]",
            )}
          >
            {l.text}
          </li>
        ))}
      </ul>
    </section>
  );
});
