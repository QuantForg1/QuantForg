"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BarChart3, RefreshCw } from "lucide-react";
import { SignalsReferenceDesk } from "@/components/trading/signals-reference-desk";
import { mt5Api, signalCenterApi } from "@/lib/api/endpoints";
import { asRecord, num } from "@/lib/desk";
import { cn } from "@/lib/utils";
import { SignalsLockedView } from "@/components/billing/feature-locked";
import { isSubscriptionRequiredError } from "@/lib/billing/feature-access";
import { isGoldSymbol, TRADING_SYMBOL } from "@/lib/trading/gold-only";
import {
  normalizeSignalCenterPayload,
  SIGNAL_CENTER_QUERY_KEY,
  sortSignalRows,
  TRADER_POLL_MS,
} from "@/lib/trading/trader-ux";

function clockLabel(raw: unknown): string {
  if (raw == null || raw === "") return "Not available";
  const ms = typeof raw === "number" ? raw : Date.parse(String(raw));
  if (!Number.isFinite(ms)) return "Not available";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(ms);
}

export function SignalsWorkspace() {
  const [autoRefresh, setAutoRefresh] = useState(true);

  const signalsQ = useQuery({
    queryKey: SIGNAL_CENTER_QUERY_KEY,
    queryFn: () => signalCenterApi.list({ enabled_only: false }),
    retry: false,
    refetchInterval: autoRefresh ? TRADER_POLL_MS : false,
    placeholderData: (prev) => prev,
  });
  const quoteQ = useQuery({
    queryKey: ["signals-gold-quote", TRADING_SYMBOL],
    queryFn: () => mt5Api.researchTick(TRADING_SYMBOL),
    retry: false,
    refetchInterval: autoRefresh ? TRADER_POLL_MS : false,
    placeholderData: (prev) => prev,
  });

  const normalized = useMemo(
    () =>
      normalizeSignalCenterPayload(
        signalsQ.isError && !signalsQ.data ? null : asRecord(signalsQ.data),
      ),
    [signalsQ.data, signalsQ.isError],
  );

  const primary = useMemo(() => {
    const gold = normalized.rows.filter((row) =>
      isGoldSymbol(String(row.broker_symbol || row.symbol || "")),
    );
    const issued = sortSignalRows(gold, "strongest")[0];
    if (issued) return issued;
    const payload = asRecord(signalsQ.data);
    const items = Array.isArray(payload.items) ? payload.items : [];
    const raw = items.find(
      (item) =>
        item != null &&
        typeof item === "object" &&
        isGoldSymbol(String((item as Record<string, unknown>).symbol || "")),
    );
    if (!raw || typeof raw !== "object") return null;
    const item = raw as Record<string, unknown>;
    return {
      symbol: item.symbol,
      broker_symbol: item.symbol,
      direction: item.direction,
      badge: item.badge,
      status: item.status,
      current_price: item.current_price,
      entry: item.entry,
      stop_loss: item.stop_loss ?? item.stop,
      take_profit: item.take_profit ?? item.target,
      RR: item.RR ?? item.rr,
      rr: item.rr ?? item.RR,
      ai_confidence: item.confidence,
      confidence: item.confidence,
      explanation: item.ai_explanation ?? item.reasoning,
      reason: item.reasoning ?? item.ai_explanation,
      timestamp: item.time_generated,
      as_of: item.time_generated,
      opportunity_score: item.opportunity_score,
    };
  }, [normalized.rows, signalsQ.data]);

  const quoteRecord = asRecord(quoteQ.data);
  const quote = num(quoteRecord.bid);
  const quoteAt = quoteRecord.timestamp ?? quoteRecord.as_of;

  const updatedAt = quoteAt || (primary
    ? primary.timestamp ??
      primary.features_as_of ??
      primary.as_of ??
      normalized.asOf
    : normalized.asOf);

  if (isSubscriptionRequiredError(signalsQ.error)) {
    return <SignalsLockedView />;
  }

  return (
    <div className="qf-desk min-w-0 space-y-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex min-w-0 items-start gap-3">
          <span className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[var(--accent-soft)] text-[var(--accent)]">
            <BarChart3 className="h-5 w-5" aria-hidden />
          </span>
          <div className="min-w-0">
            <h1 className="text-[1.35rem] font-semibold leading-tight tracking-tight text-[var(--fg)] sm:text-[1.85rem]">
              Signals
            </h1>
            <p className="mt-1 max-w-xl text-sm leading-relaxed text-[var(--fg-muted)]">
              High-probability trading signal from QuantForg&apos;s institutional intelligence.
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-3 sm:justify-end">
          <p className="inline-flex items-center gap-2 text-xs text-[var(--fg-muted)]">
            <button
              type="button"
              className="inline-flex h-11 w-11 items-center justify-center rounded-full text-[var(--fg-muted)] hover:bg-[var(--surface-2)] hover:text-[var(--fg)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
              aria-label="Refresh analysis"
              disabled={signalsQ.isFetching || quoteQ.isFetching}
              onClick={() => {
                void signalsQ.refetch();
                void quoteQ.refetch();
              }}
            >
              <RefreshCw
                className={cn(
                  "h-4 w-4",
                  (signalsQ.isFetching || quoteQ.isFetching) && "animate-spin",
                )}
                aria-hidden
              />
            </button>
            Last Update: {clockLabel(updatedAt)}
          </p>
          <div className="inline-flex items-center gap-2 text-sm text-[var(--fg)]">
            <span id="signal-auto-refresh-label">Auto Refresh</span>
            <button
              type="button"
              role="switch"
              aria-checked={autoRefresh}
              aria-labelledby="signal-auto-refresh-label"
              onClick={() => setAutoRefresh((on) => !on)}
              className={cn(
                "relative h-6 w-11 shrink-0 rounded-full transition-colors duration-[var(--duration-fast)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]",
                autoRefresh ? "bg-[var(--accent)]" : "bg-[var(--surface-3)]",
              )}
            >
              <span
                className={cn(
                  "absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-transform duration-[var(--duration-fast)]",
                  autoRefresh && "translate-x-5",
                )}
              />
            </button>
          </div>
        </div>
      </div>

      <SignalsReferenceDesk
        row={primary}
        quote={Number.isFinite(quote) ? quote : null}
        loading={signalsQ.isLoading && primary == null && !Number.isFinite(quote)}
        unavailable={signalsQ.isError && primary == null}
      />
    </div>
  );
}
