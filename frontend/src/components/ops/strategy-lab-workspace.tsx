"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { FlaskConical, Shield } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { strategyLabApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

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

export function StrategyLabWorkspace() {
  const qc = useQueryClient();
  const [strategyKey, setStrategyKey] = useState("trend_following");
  const [caseId, setCaseId] = useState("");
  const [validation, setValidation] = useState<Record<string, unknown> | null>(
    null,
  );
  const [comparison, setComparison] = useState<Record<string, unknown> | null>(
    null,
  );
  const [replay, setReplay] = useState<Record<string, unknown> | null>(null);

  const statusQ = useQuery({
    queryKey: ["strategy-lab-status"],
    queryFn: () => strategyLabApi.status(),
    staleTime: 30_000,
  });

  const registryQ = useQuery({
    queryKey: ["strategy-lab-registry"],
    queryFn: () => strategyLabApi.registry(),
    staleTime: 30_000,
  });

  const promoQ = useQuery({
    queryKey: ["strategy-lab-promotion"],
    queryFn: () => strategyLabApi.promotionDashboard(),
    staleTime: 15_000,
  });

  const validateM = useMutation({
    mutationFn: () =>
      strategyLabApi.validate({
        strategy_key: strategyKey,
        profit_factor: 1.4,
        sharpe: 0.8,
        max_drawdown_pct: 12,
        trade_count: 40,
        win_rate: 55,
        stability: 0.7,
      }),
    onSuccess: (data) => {
      setValidation(data);
      toast.success("Validation report generated (lab only)");
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Validate failed"),
  });

  const compareM = useMutation({
    mutationFn: () =>
      strategyLabApi.compare([
        {
          strategy_key: strategyKey,
          run_id: "lab_a",
          profit_factor: 1.5,
          sharpe: 0.9,
          max_drawdown_pct: 10,
          trade_count: 50,
          win_rate: 56,
          net_pnl: 120,
        },
        {
          strategy_key: "mean_reversion",
          run_id: "lab_b",
          profit_factor: 1.1,
          sharpe: 0.4,
          max_drawdown_pct: 18,
          trade_count: 30,
          win_rate: 48,
          net_pnl: -20,
        },
      ]),
    onSuccess: (data) => setComparison(data),
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Compare failed"),
  });

  const replayLoadM = useMutation({
    mutationFn: () =>
      strategyLabApi.replayLoad({
        strategy_key: strategyKey,
        bars: [
          {
            time: "2026-07-21T10:00:00Z",
            open: 4000,
            high: 4005,
            low: 3998,
            close: 4002,
            volume: 100,
          },
          {
            time: "2026-07-21T11:00:00Z",
            open: 4002,
            high: 4008,
            low: 4000,
            close: 4006,
            volume: 120,
          },
          {
            time: "2026-07-21T12:00:00Z",
            open: 4006,
            high: 4010,
            low: 4004,
            close: 4009,
            volume: 90,
          },
        ],
      }),
    onSuccess: (data) => {
      setReplay(data);
      toast.info("Replay loaded — lab bars only");
    },
  });

  const openPromoM = useMutation({
    mutationFn: () =>
      strategyLabApi.promotionOpen({
        strategy_key: strategyKey,
        profit_factor: 1.4,
        sharpe: 0.8,
        max_drawdown_pct: 12,
        trade_count: 40,
        win_rate: 55,
        stability: 0.7,
        validation_passed: true,
      }),
    onSuccess: async (data) => {
      setCaseId(str(data.case_id, ""));
      toast.success("Promotion case opened");
      await qc.invalidateQueries({ queryKey: ["strategy-lab-promotion"] });
      await qc.invalidateQueries({ queryKey: ["strategy-lab-registry"] });
    },
  });

  const approveM = useMutation({
    mutationFn: (decision: "approve" | "reject") =>
      strategyLabApi.promotionApprove({
        case_id: caseId,
        decision,
        operator: "desk_operator",
        reason: decision === "approve" ? "Scorecard + validation ok" : "Rejected",
      }),
    onSuccess: async () => {
      toast.success("Operator decision recorded (lab only)");
      await qc.invalidateQueries({ queryKey: ["strategy-lab-promotion"] });
      await qc.invalidateQueries({ queryKey: ["strategy-lab-registry"] });
      await qc.invalidateQueries({ queryKey: ["strategy-lab-status"] });
    },
  });

  const versionM = useMutation({
    mutationFn: () =>
      strategyLabApi.versionRecord({
        strategy_key: strategyKey,
        version: "1.0.1-lab",
        parameters: { atr_period: 14, ema_fast: 20 },
        notes: "Sandbox version — not production",
        created_by: "desk_operator",
      }),
    onSuccess: () => toast.success("Version recorded in lab history"),
  });

  const experimentM = useMutation({
    mutationFn: () =>
      strategyLabApi.experimentCreate({
        strategy_key: strategyKey,
        variants: [
          { label: "tight", parameters: { sl: 0.0015, tp: 0.003 } },
          { label: "wide", parameters: { sl: 0.003, tp: 0.006 } },
        ],
      }),
    onSuccess: () => toast.success("Experiment batch created (sandbox)"),
  });

  const caps = useMemo(() => {
    const raw = asRecord(statusQ.data?.capabilities);
    return Object.entries(raw)
      .filter(
        ([k]) =>
          !["broker_order_submit", "affects_production_positions"].includes(k),
      )
      .map(([k, v]) => ({
        key: k,
        on: Boolean(v),
        label: k.replace(/_/g, " "),
      }));
  }, [statusQ.data]);

  if (statusQ.isLoading) return <DeskSkeleton rows={6} />;
  if (statusQ.isError) {
    return (
      <DeskError
        message={
          statusQ.error instanceof ApiError
            ? statusQ.error.message
            : "Could not load Strategy Lab."
        }
        onRetry={() => void statusQ.refetch()}
      />
    );
  }

  const status = statusQ.data ?? {};
  const strategies = asList(asRecord(registryQ.data).strategies);
  const promo = asRecord(promoQ.data);
  const report = asRecord(asRecord(validation).report);
  const scorecard = asRecord(asRecord(validation).scorecard);

  return (
    <div className="grid gap-3 lg:grid-cols-12">
      <div className="space-y-3 lg:col-span-8">
        <Panel
          title="Mission"
          action={
            <Badge tone="neutral" className="font-mono text-[10px]">
              {str(status.version, "strategy-research-lab-v1")}
            </Badge>
          }
        >
          <div className="flex items-start gap-3">
            <FlaskConical className="mt-0.5 h-4 w-4 shrink-0 text-[var(--fg-subtle)]" />
            <div className="space-y-2">
              <p className="text-[13px] leading-relaxed text-[var(--fg)]">
                {str(
                  asRecord(status.config).mission,
                  "Validate and promote strategies before production.",
                )}
              </p>
              <p className="text-[11px] text-[var(--fg-subtle)]">
                {str(status.disclaimer, "")}
              </p>
              <div className="flex flex-wrap gap-2">
                <Badge tone="success">lab isolated</Badge>
                <Badge tone="neutral">never order_send</Badge>
                <Badge tone="warning">no mock production metrics</Badge>
              </div>
            </div>
          </div>
        </Panel>

        <Panel
          title="Lab controls"
          action={
            <Input
              className="h-8 w-44 font-mono text-xs"
              value={strategyKey}
              onChange={(e) => setStrategyKey(e.target.value)}
              aria-label="Strategy key"
            />
          }
        >
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              disabled={validateM.isPending}
              onClick={() => validateM.mutate()}
            >
              Validate + scorecard
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={compareM.isPending}
              onClick={() => compareM.mutate()}
            >
              Compare runs
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={replayLoadM.isPending}
              onClick={() => replayLoadM.mutate()}
            >
              Load replay
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={!replay}
              onClick={async () => {
                const data = await strategyLabApi.replayControl("step");
                setReplay(data);
              }}
            >
              Step replay
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={experimentM.isPending}
              onClick={() => experimentM.mutate()}
            >
              Parameter experiment
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={versionM.isPending}
              onClick={() => versionM.mutate()}
            >
              Record version
            </Button>
            <Button
              size="sm"
              variant="secondary"
              disabled={openPromoM.isPending}
              onClick={() => openPromoM.mutate()}
            >
              Open promotion
            </Button>
            <Button
              size="sm"
              disabled={!caseId || approveM.isPending}
              onClick={() => approveM.mutate("approve")}
            >
              Operator approve
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={!caseId || approveM.isPending}
              onClick={() => approveM.mutate("reject")}
            >
              Operator reject
            </Button>
          </div>
          {caseId ? (
            <p className="mt-2 font-mono text-[11px] text-[var(--fg-muted)]">
              case_id={caseId}
            </p>
          ) : null}
        </Panel>

        {validation ? (
          <Panel title="Explainable validation report">
            <div className="mb-2 flex flex-wrap gap-2">
              <Badge tone={scorecard.passed ? "success" : "danger"}>
                score {str(scorecard.score)}
              </Badge>
              <Badge tone="neutral">{str(report.summary)}</Badge>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <h3 className="mb-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                  Why valid
                </h3>
                <ul className="list-inside list-disc text-[12px] text-[var(--fg-muted)]">
                  {asList(report.why_valid)
                    .map(String)
                    .map((x) => (
                      <li key={x}>{x}</li>
                    ))}
                </ul>
              </div>
              <div>
                <h3 className="mb-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                  Why invalid
                </h3>
                <ul className="list-inside list-disc text-[12px] text-[var(--fg-muted)]">
                  {asList(report.why_invalid).length === 0 ? (
                    <li>No blocking weaknesses.</li>
                  ) : (
                    asList(report.why_invalid)
                      .map(String)
                      .map((x) => <li key={x}>{x}</li>)
                  )}
                </ul>
              </div>
            </div>
            <p className="mt-3 text-[11px] text-[var(--fg-subtle)]">
              {str(report.disclaimer)}
            </p>
          </Panel>
        ) : (
          <DeskEmpty
            icon={Shield}
            title="No validation yet"
            description="Run Validate to build a scorecard and explainable report from supplied lab metrics."
          />
        )}

        {comparison ? (
          <Panel title="Strategy comparison">
            <pre className="overflow-auto font-mono text-[11px] text-[var(--fg-muted)]">
              {JSON.stringify(comparison, null, 2)}
            </pre>
          </Panel>
        ) : null}
      </div>

      <div className="space-y-3 lg:col-span-4">
        <Panel title="Capabilities (10)">
          {caps.map((c) => (
            <div
              key={c.key}
              className="flex items-center justify-between gap-2 border-b border-[var(--border)]/60 py-1.5 last:border-0"
            >
              <span className="text-[12px] text-[var(--fg-muted)]">{c.label}</span>
              <Badge tone={c.on ? "success" : "neutral"}>
                {c.on ? "ON" : "OFF"}
              </Badge>
            </div>
          ))}
        </Panel>
        <Panel title="Strategy registry">
          <div className="max-h-64 space-y-1 overflow-auto">
            {strategies.length === 0 ? (
              <DeskEmpty
                icon={FlaskConical}
                title="Empty registry"
                description="No strategies registered."
              />
            ) : (
              strategies.slice(0, 12).map((row, i) => {
                const r = asRecord(row);
                return (
                  <button
                    key={`${str(r.key)}-${i}`}
                    type="button"
                    className={cn(
                      "flex w-full items-center justify-between border border-[var(--border)] px-2 py-1 text-left text-[12px]",
                      str(r.key) === strategyKey && "border-[var(--accent)]",
                    )}
                    onClick={() => setStrategyKey(str(r.key))}
                  >
                    <span className="font-mono">{str(r.key)}</span>
                    <Badge tone="neutral">{str(r.status)}</Badge>
                  </button>
                );
              })
            )}
          </div>
        </Panel>
        <Panel title="Promotion dashboard">
          <pre className="max-h-48 overflow-auto font-mono text-[11px] text-[var(--fg-muted)]">
            {JSON.stringify(promo, null, 2)}
          </pre>
        </Panel>
        <Panel title="Replay state">
          <pre className="max-h-40 overflow-auto font-mono text-[11px] text-[var(--fg-muted)]">
            {JSON.stringify(replay ?? { state: "idle" }, null, 2)}
          </pre>
        </Panel>
      </div>
    </div>
  );
}
