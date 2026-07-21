"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Scale, Shield } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import {
  institutionalDecisionApi,
  mt5Api,
  portfolioApi,
} from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, num, str } from "@/lib/desk";
import { TRADING_SYMBOL } from "@/lib/trading/gold-only";
import { useTradingSession } from "@/providers/trading-session-provider";
import { cn, formatNumber } from "@/lib/utils";

function Panel({
  title,
  children,
  action,
}: {
  title: string;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <section className="border border-[var(--border)] bg-[var(--surface)]">
      <header className="flex items-center justify-between gap-2 border-b border-[var(--border)] px-3 py-2">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          {title}
        </h2>
        {action}
      </header>
      <div className="p-3">{children}</div>
    </section>
  );
}

export function InstitutionalDecisionWorkspace() {
  const session = useTradingSession();
  const [side, setSide] = useState<"buy" | "sell">("buy");
  const [dryRun, setDryRun] = useState(true);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  const statusQ = useQuery({
    queryKey: ["institutional-decision-status"],
    queryFn: () => institutionalDecisionApi.status(),
    staleTime: 30_000,
  });

  const portfolioQ = useQuery({
    queryKey: ["portfolio-institutional-decision"],
    queryFn: () => portfolioApi.get(),
    staleTime: 15_000,
  });

  const tickQ = useQuery({
    queryKey: ["mt5-tick", TRADING_SYMBOL, "institutional-decision"],
    queryFn: () => mt5Api.tick(TRADING_SYMBOL),
    enabled: session.connected,
    staleTime: 2_000,
    refetchInterval: session.connected ? 5_000 : false,
    retry: false,
  });

  const evaluateM = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      institutionalDecisionApi.evaluate(body),
    onSuccess: (data) => {
      setResult(data);
      const decision = str(data.decision, "WAIT");
      if (decision === "TRADE_IDEA") {
        toast.success("TRADE_IDEA (dry-run) — no order sent");
      } else if (decision === "SUSPENDED") {
        toast.error("Strategy suspended by health gate");
      } else {
        toast.info("WAIT — capital preservation");
      }
    },
    onError: (err) => {
      toast.error(err instanceof ApiError ? err.message : "Evaluate failed");
    },
  });

  const equity = num(asRecord(portfolioQ.data?.account).equity, 0);
  const tick = asRecord(tickQ.data);
  const bid = num(tick.bid);
  const ask = num(tick.ask);
  const spread =
    Number.isFinite(bid) && Number.isFinite(ask) && ask >= bid
      ? Number((ask - bid).toFixed(2))
      : null;
  const mid =
    Number.isFinite(bid) && Number.isFinite(ask)
      ? Number(((bid + ask) / 2).toFixed(2))
      : null;

  const pipeline = useMemo(
    () => asList(statusQ.data?.pipeline).map(String),
    [statusQ.data],
  );

  const runEvaluate = (withRiskSafety: boolean) => {
    evaluateM.mutate({
      side,
      dry_run: dryRun,
      strategy_id: "institutional-decision-v1",
      equity: equity || 10000,
      stop_distance: 5,
      spread,
      atr: mid != null ? Number((mid * 0.002).toFixed(2)) : 8,
      price: mid,
      consecutive_losses: 0,
      daily_drawdown_pct: 0,
      risk_engine_passed: withRiskSafety ? true : null,
      safety_engine_passed: withRiskSafety ? true : null,
      layers: {
        trend_aligned: true,
        trend_label: "bullish",
        structure_valid: true,
        structure_bias: "bullish",
        liquidity_ok: true,
        order_block_valid: true,
        fvg_valid: true,
        spread,
        atr: mid != null ? Number((mid * 0.002).toFixed(2)) : 8,
        price: mid,
        risk_engine_passed: withRiskSafety ? true : null,
        safety_engine_passed: withRiskSafety ? true : null,
      },
    });
  };

  if (statusQ.isLoading) return <DeskSkeleton rows={6} />;
  if (statusQ.isError) {
    return (
      <DeskError
        message={
          statusQ.error instanceof ApiError
            ? statusQ.error.message
            : "Could not load Decision Engine V1."
        }
        onRetry={() => void statusQ.refetch()}
      />
    );
  }

  const status = statusQ.data ?? {};
  const card = asRecord(asRecord(result).card);
  const layers = asList(asRecord(result).layers);
  const confidence = asRecord(asRecord(result).confidence);
  const adaptive = asRecord(asRecord(result).adaptive_risk);
  const loss = asRecord(asRecord(result).loss_protection);
  const health = asRecord(asRecord(result).health);
  const decision = str(asRecord(result).decision, "");

  return (
    <div className="grid gap-3 lg:grid-cols-12">
      <div className="space-y-3 lg:col-span-8">
        <Panel
          title="Mission"
          action={
            <Badge tone="neutral" className="font-mono text-[10px]">
              {str(status.version, "institutional-ai-decision-v1")}
            </Badge>
          }
        >
          <div className="flex items-start gap-3">
            <Scale className="mt-0.5 h-4 w-4 shrink-0 text-[var(--fg-subtle)]" />
            <div className="space-y-2">
              <p className="text-[13px] leading-relaxed text-[var(--fg)]">
                {str(
                  status.mission,
                  "Capital preservation and disciplined execution decisions.",
                )}
              </p>
              <p className="text-[11px] text-[var(--fg-subtle)]">
                {str(status.disclaimer, "")}
              </p>
              <p className="font-mono text-[11px] text-[var(--fg-muted)]">
                {pipeline.join(" → ") ||
                  "trend → structure → liquidity → OB → FVG → session → spread → risk → safety"}
              </p>
            </div>
          </div>
        </Panel>

        <Panel
          title="Dry-run evaluate"
          action={
            <div className="flex flex-wrap gap-1">
              <Button
                size="sm"
                variant={side === "buy" ? "default" : "outline"}
                onClick={() => setSide("buy")}
              >
                Buy
              </Button>
              <Button
                size="sm"
                variant={side === "sell" ? "default" : "outline"}
                onClick={() => setSide("sell")}
              >
                Sell
              </Button>
              <Button
                size="sm"
                variant={dryRun ? "secondary" : "outline"}
                onClick={() => setDryRun(true)}
              >
                Dry-run ON
              </Button>
            </div>
          }
        >
          <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
            <div className="border border-[var(--border)] px-2 py-1.5">
              <div className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                Equity
              </div>
              <div className="font-mono text-[13px]">
                {equity ? formatNumber(equity, 2) : "—"}
              </div>
            </div>
            <div className="border border-[var(--border)] px-2 py-1.5">
              <div className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                Spread
              </div>
              <div className="font-mono text-[13px]">
                {spread != null ? formatNumber(spread, 2) : "—"}
              </div>
            </div>
            <div className="border border-[var(--border)] px-2 py-1.5">
              <div className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                Mid
              </div>
              <div className="font-mono text-[13px]">
                {mid != null ? formatNumber(mid, 2) : "—"}
              </div>
            </div>
            <div className="border border-[var(--border)] px-2 py-1.5">
              <div className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                Mode
              </div>
              <div className="font-mono text-[11px] text-[var(--fg-muted)]">
                Dry-run · no order_send
              </div>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              disabled={evaluateM.isPending}
              onClick={() => runEvaluate(false)}
            >
              Evaluate (fail-closed Risk/Safety)
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={evaluateM.isPending}
              onClick={() => runEvaluate(true)}
            >
              Simulate Risk+Safety ALLOW
            </Button>
          </div>
          {!result ? (
            <div className="mt-3">
              <DeskEmpty
                icon={Shield}
                title="No decision yet"
                description="Dry-run validates the multi-layer pipeline without sending orders. Risk and Safety are never bypassed."
              />
            </div>
          ) : (
            <div className="mt-3 space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge
                  tone={
                    decision === "TRADE_IDEA"
                      ? "success"
                      : decision === "SUSPENDED"
                        ? "danger"
                        : "warning"
                  }
                >
                  {decision || "—"}
                </Badge>
                <Badge tone="neutral">
                  confidence {str(confidence.score)} ({str(confidence.band)})
                </Badge>
                <Badge tone={asRecord(result).dry_run ? "accent" : "warning"}>
                  {asRecord(result).dry_run ? "dry-run" : "live-path advisory"}
                </Badge>
              </div>
              <p className="text-[12px] text-[var(--fg-muted)]">
                {str(card.headline)}
              </p>
              <div className="grid gap-1 sm:grid-cols-3">
                {layers.map((row, i) => {
                  const r = asRecord(row);
                  return (
                    <div
                      key={`${str(r.name)}-${i}`}
                      className={cn(
                        "border px-2 py-1.5",
                        r.passed
                          ? "border-[var(--border)]"
                          : "border-[var(--danger)]/40",
                      )}
                    >
                      <div className="flex items-center justify-between gap-1">
                        <span className="font-mono text-[10px] uppercase">
                          {str(r.name)}
                        </span>
                        <Badge tone={r.passed ? "success" : "danger"}>
                          {r.passed ? "pass" : "block"}
                        </Badge>
                      </div>
                      <p className="mt-1 text-[10px] text-[var(--fg-subtle)]">
                        {str(r.reason)}
                      </p>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </Panel>

        {result ? (
          <Panel title="Explainable decision card">
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <h3 className="mb-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                  Why accepted
                </h3>
                <ul className="list-inside list-disc text-[12px] text-[var(--fg-muted)]">
                  {asList(card.why_accepted)
                    .map(String)
                    .slice(0, 6)
                    .map((x) => (
                      <li key={x}>{x}</li>
                    ))}
                </ul>
              </div>
              <div>
                <h3 className="mb-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                  Why rejected
                </h3>
                <ul className="list-inside list-disc text-[12px] text-[var(--fg-muted)]">
                  {asList(card.why_rejected).length === 0 ? (
                    <li>No blocking reasons on this pass.</li>
                  ) : (
                    asList(card.why_rejected)
                      .map(String)
                      .slice(0, 6)
                      .map((x) => <li key={x}>{x}</li>)
                  )}
                </ul>
              </div>
            </div>
            <p className="mt-3 text-[11px] text-[var(--fg-subtle)]">
              {str(card.disclaimer)}
            </p>
          </Panel>
        ) : null}
      </div>

      <div className="space-y-3 lg:col-span-4">
        <Panel title="Adaptive risk">
          <pre className="overflow-auto font-mono text-[11px] text-[var(--fg-muted)]">
            {JSON.stringify(adaptive, null, 2)}
          </pre>
        </Panel>
        <Panel title="Loss protection">
          <pre className="overflow-auto font-mono text-[11px] text-[var(--fg-muted)]">
            {JSON.stringify(loss, null, 2)}
          </pre>
        </Panel>
        <Panel title="Strategy health">
          <pre className="overflow-auto font-mono text-[11px] text-[var(--fg-muted)]">
            {JSON.stringify(health, null, 2)}
          </pre>
        </Panel>
      </div>
    </div>
  );
}
