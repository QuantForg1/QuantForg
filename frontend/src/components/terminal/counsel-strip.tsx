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
 * Always-on institutional decision layer — not a chatbot.
 * Grounded in live session + quotes; optional intelligence context when available.
 * Never invents prices or trades.
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
    staleTime: 60_000,
  });

  const items = useMemo((): CounselItem[] => {
    const next: CounselItem[] = [
      {
        id: "session",
        label: session.connected ? "Session attached" : "Attach broker session",
        tone: session.connected ? "ok" : "block",
      },
      {
        id: "quote",
        label: hasQuote
          ? `Quote live · spr ${spread.toFixed(5)}`
          : session.connected
            ? "Awaiting quote"
            : "No quote",
        tone: hasQuote ? "ok" : session.connected ? "warn" : "neutral",
      },
      {
        id: "margin",
        label:
          session.connected && Number.isFinite(free)
            ? free > 0
              ? "Free margin available"
              : "Free margin exhausted"
            : "Margin unknown",
        tone:
          !session.connected || !Number.isFinite(free)
            ? "neutral"
            : free > 0
              ? "ok"
              : "block",
      },
      {
        id: "level",
        label:
          session.connected && Number.isFinite(marginLevel) && marginLevel > 0
            ? marginLevel < 100
              ? `Margin level ${marginLevel.toFixed(0)}% — elevated risk`
              : `Margin level ${marginLevel.toFixed(0)}%`
            : "Margin level —",
        tone:
          session.connected && Number.isFinite(marginLevel) && marginLevel > 0 && marginLevel < 100
            ? "warn"
            : "neutral",
      },
    ];

    if (contextQ.isSuccess) {
      const ctx = asRecord(contextQ.data);
      const risks = asList(ctx.risk_factors ?? ctx.risks ?? ctx.warnings).map((v) =>
        str(v),
      );
      const narrative = str(ctx.summary ?? ctx.narrative ?? ctx.headline);
      if (risks[0]) {
        next.push({
          id: "intel-risk",
          label: risks[0].slice(0, 120),
          tone: "warn",
        });
      } else if (narrative) {
        next.push({
          id: "intel",
          label: narrative.slice(0, 120),
          tone: "neutral",
        });
      }
    } else if (contextQ.isError) {
      next.push({
        id: "intel-empty",
        label: "Counsel context unavailable",
        tone: "neutral",
      });
    }

    return next;
  }, [
    session.connected,
    hasQuote,
    spread,
    free,
    marginLevel,
    contextQ.isSuccess,
    contextQ.isError,
    contextQ.data,
  ]);

  const blocked = items.some((i) => i.tone === "block");
  const warned = items.some((i) => i.tone === "warn");

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
            Counsel{" "}
            <span
              className={cn(
                "tabular",
                blocked && "text-[var(--danger)]",
                !blocked && warned && "text-[var(--warning)]",
                !blocked && !warned && "text-[var(--success)]",
              )}
            >
              {blocked ? "blocked" : warned ? "caution" : "clear"}
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
      aria-label="AI Counsel"
    >
      <header className="mb-1.5 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Scale className="h-3.5 w-3.5 text-[var(--accent)]" aria-hidden />
          <h2 className="qf-label text-[var(--fg)]">Counsel</h2>
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
