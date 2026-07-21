"use client";

import { memo, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Scale } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useTradingSession } from "@/providers/trading-session-provider";
import { intelligenceApi } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

type CounselItem = {
  id: string;
  label: string;
  tone: "ok" | "warn" | "block" | "neutral";
};

/**
 * Quiet counsel strip — status only when collapsed; expand for details.
 * Never invents prices or trades. Collapsed by default so chart stays primary.
 */
export const TerminalCounselStrip = memo(function TerminalCounselStrip({
  symbol,
  bid,
  ask,
  collapsed,
  onToggle,
  className,
}: {
  symbol: string;
  bid?: number;
  ask?: number;
  collapsed: boolean;
  onToggle: () => void;
  className?: string;
}) {
  const session = useTradingSession();
  const free = num(session.freeMargin);
  const marginLevel = num(session.marginLevel);
  const hasQuote =
    typeof bid === "number" &&
    typeof ask === "number" &&
    Number.isFinite(bid) &&
    Number.isFinite(ask);
  const spread = hasQuote && bid != null && ask != null ? ask - bid : NaN;

  const contextQ = useQuery({
    queryKey: ["terminal-counsel", symbol],
    queryFn: () => intelligenceApi.marketContext("FX", symbol),
    retry: false,
    enabled: Boolean(symbol) && !collapsed,
    staleTime: 120_000,
  });

  const items = useMemo((): CounselItem[] => {
    const next: CounselItem[] = [
      {
        id: "session",
        label: session.connected ? "Session attached" : "Attach broker",
        tone: session.connected ? "ok" : "block",
      },
      {
        id: "quote",
        label: hasQuote
          ? `Live · spr ${spread.toFixed(5)}`
          : session.connected
            ? "Awaiting quote"
            : "No quote",
        tone: hasQuote ? "ok" : session.connected ? "warn" : "neutral",
      },
    ];

    if (session.connected && Number.isFinite(free)) {
      next.push({
        id: "margin",
        label: free > 0 ? "Margin ok" : "Margin exhausted",
        tone: free > 0 ? "ok" : "block",
      });
    }

    if (session.connected && Number.isFinite(marginLevel) && marginLevel > 0 && marginLevel < 100) {
      next.push({
        id: "level",
        label: `Margin ${marginLevel.toFixed(0)}%`,
        tone: "warn",
      });
    }

    if (contextQ.isSuccess) {
      const ctx = asRecord(contextQ.data);
      const risks = asList(ctx.risk_factors ?? ctx.risks ?? ctx.warnings).map((v) =>
        str(v),
      );
      if (risks[0]) {
        next.push({
          id: "intel-risk",
          label: risks[0].slice(0, 80),
          tone: "warn",
        });
      }
    }

    return next;
  }, [
    session.connected,
    hasQuote,
    spread,
    free,
    marginLevel,
    contextQ.isSuccess,
    contextQ.data,
  ]);

  const blocked = items.some((i) => i.tone === "block");
  const warned = items.some((i) => i.tone === "warn");

  if (collapsed) {
    return (
      <div
        className={cn(
          "flex h-7 shrink-0 items-center justify-between border-b border-[var(--border)]/70 bg-[var(--bg)] px-3",
          className,
        )}
      >
        <button
          type="button"
          className="flex items-center gap-2 text-left"
          onClick={onToggle}
          aria-expanded={false}
        >
          <Scale className="h-3 w-3 text-[var(--fg-subtle)]" aria-hidden />
          <span className="qf-caption">
            AI{" "}
            <span
              className={cn(
                "tabular",
                blocked && "text-[var(--danger)]",
                !blocked && warned && "text-[var(--warning)]",
                !blocked && !warned && "text-[var(--success)]",
              )}
            >
              {blocked ? "block" : warned ? "caution" : "clear"}
            </span>
          </span>
        </button>
        <Button size="sm" variant="ghost" className="h-6 px-2 text-[10px]" data-compact onClick={onToggle}>
          Show
        </Button>
      </div>
    );
  }

  return (
    <section
      className={cn(
        "shrink-0 border-b border-[var(--border)]/70 bg-[var(--bg)] px-3 py-1.5",
        className,
      )}
      aria-label="AI counsel"
    >
      <header className="mb-1 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Scale className="h-3 w-3 text-[var(--fg-subtle)]" aria-hidden />
          <h2 className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-muted)]">
            Counsel
          </h2>
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
        <Button size="sm" variant="ghost" className="h-6 px-2 text-[10px]" data-compact onClick={onToggle}>
          Hide
        </Button>
      </header>
      <ul className="flex flex-wrap gap-x-3 gap-y-0.5">
        {items.map((item) => (
          <li
            key={item.id}
            className={cn(
              "text-[11px] leading-snug",
              item.tone === "ok" && "text-[var(--success)]",
              item.tone === "warn" && "text-[var(--warning)]",
              item.tone === "block" && "text-[var(--danger)]",
              item.tone === "neutral" && "text-[var(--fg-muted)]",
            )}
          >
            {item.label}
          </li>
        ))}
      </ul>
    </section>
  );
});
