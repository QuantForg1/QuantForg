"use client";

import { useAuth } from "@/providers/auth-provider";
import { isPrivilegedRole } from "@/lib/navigation/customer-routes";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { aiTradingIntelligenceApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { TRADING_SYMBOL } from "@/lib/trading/gold-only";

type Tab =
  | "market"
  | "regime"
  | "signals"
  | "optimizer"
  | "health"
  | "risk"
  | "supervisor";

const TABS: { id: Tab; label: string }[] = [
  { id: "market", label: "Market intel" },
  { id: "regime", label: "Regime" },
  { id: "signals", label: "Signal quality" },
  { id: "optimizer", label: "Optimizer" },
  { id: "health", label: "Strategy health" },
  { id: "risk", label: "AI risk" },
  { id: "supervisor", label: "Supervisor" },
];

/**
 * Phase 4 AI Trading Intelligence desks — RC4, explainable, no fake live AI.
 */
export function Phase4AtiDesk() {
  const { user } = useAuth();
  const canChangeMode = isPrivilegedRole(user?.role);
  const [tab, setTab] = useState<Tab>("market");
  const qc = useQueryClient();

  const healthQ = useQuery({
    queryKey: ["ati-health"],
    queryFn: aiTradingIntelligenceApi.health,
    retry: false,
    staleTime: 15_000,
  });
  const supervisorQ = useQuery({
    queryKey: ["ati-supervisor"],
    queryFn: aiTradingIntelligenceApi.supervisor,
    retry: false,
    staleTime: 10_000,
  });
  const marketQ = useQuery({
    queryKey: ["ati-market", TRADING_SYMBOL],
    queryFn: () =>
      aiTradingIntelligenceApi.marketIntelligence({
        symbol: TRADING_SYMBOL,
        facts: {
          regime_label: "unknown",
          regime_confidence: 40,
          data_sources: ["caller_facts"],
          confidence: 40,
        },
      }),
    retry: false,
    staleTime: 30_000,
    enabled: tab === "market",
  });
  const regimeValQ = useQuery({
    queryKey: ["ati-regime-validation"],
    queryFn: aiTradingIntelligenceApi.regimeValidation,
    retry: false,
    staleTime: 60_000,
    enabled: tab === "regime",
  });
  const signalQ = useQuery({
    queryKey: ["ati-signal"],
    queryFn: () =>
      aiTradingIntelligenceApi.signalQuality({
        symbol: TRADING_SYMBOL,
        direction: "buy",
        strategy_source: "advisory",
        regime_label: "ranging",
        regime_confidence: 70,
        confidence: 62,
        quality: 58,
        supporting_factors: ["structure"],
        conflicting_factors: [],
        ttl_seconds: 120,
      }),
    retry: false,
    staleTime: 20_000,
    enabled: tab === "signals" || tab === "health",
  });
  const optQ = useQuery({
    queryKey: ["ati-optimize"],
    queryFn: () =>
      aiTradingIntelligenceApi.optimize({
        strategy_id: "gold-default",
        backtest: {
          profit_factor: "1.2",
          expectancy: "0.4",
          max_drawdown_pct: "8",
        },
        walk_forward: { profit_factor: "1.1", trades: 40 },
        out_of_sample: { profit_factor: "1.05" },
        owner_promotion_approved: false,
      }),
    retry: false,
    staleTime: 60_000,
    enabled: tab === "optimizer",
  });
  const riskQ = useQuery({
    queryKey: ["ati-risk-alerts"],
    queryFn: () =>
      aiTradingIntelligenceApi.riskAlerts({
        portfolio: { drawdown_pct: "5", consecutive_losses: 1 },
        strategy_health: { score: "55" },
      }),
    retry: false,
    staleTime: 20_000,
    enabled: tab === "risk",
  });

  const modeMut = useMutation({
    mutationFn: (mode: string) =>
      aiTradingIntelligenceApi.setSupervisorMode(mode, true),
    onSuccess: async () => {
      toast.success("Supervisor mode updated");
      await qc.invalidateQueries({ queryKey: ["ati-supervisor"] });
      await qc.invalidateQueries({ queryKey: ["ati-health"] });
    },
    onError: () => toast.error("Could not update supervisor mode"),
  });

  const health = asRecord(healthQ.data);
  const supervisor = asRecord(supervisorQ.data);
  const mode =
    str(supervisor.mode) || str(health.supervisor_mode) || "MONITOR_ONLY";

  const freshness = useMemo(() => {
    if (healthQ.isFetching) return "refreshing";
    if (healthQ.isError) return "unavailable";
    return "ok";
  }, [healthQ.isError, healthQ.isFetching]);

  return (
    <section
      className="flex min-h-0 flex-col gap-3 rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)] p-3"
      aria-label="AI Trading Intelligence"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="text-[14px] font-semibold text-[var(--fg)]">
            AI Trading Intelligence
          </h2>
          <p className="qf-caption text-[var(--fg-muted)]">
            Explainable assembly of existing engines · never auto-LIVE · scores
            are not win probabilities
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-[11px]">
          <span className="rounded border border-[var(--border)] px-2 py-0.5 font-mono">
            mode={mode}
          </span>
          <span
            className={cn(
              "rounded border border-[var(--border)] px-2 py-0.5",
              freshness === "ok"
                ? "text-[var(--fg-muted)]"
                : "text-[var(--warning)]",
            )}
          >
            data={freshness}
          </span>
        </div>
      </div>

      <div className="flex flex-wrap gap-1">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={cn(
              "rounded px-2 py-1 text-[11px]",
              tab === t.id
                ? "bg-[var(--accent-muted)] text-[var(--accent)]"
                : "text-[var(--fg-muted)] hover:text-[var(--fg)]",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "market" ? (
        <MarketPanel
          data={asRecord(marketQ.data)}
          loading={marketQ.isLoading}
        />
      ) : null}
      {tab === "regime" ? (
        <RegimePanel
          data={asRecord(regimeValQ.data)}
          loading={regimeValQ.isLoading}
        />
      ) : null}
      {tab === "signals" || tab === "health" ? (
        <SignalPanel
          data={asRecord(signalQ.data)}
          loading={signalQ.isLoading}
        />
      ) : null}
      {tab === "optimizer" ? (
        <OptimizerPanel data={asRecord(optQ.data)} loading={optQ.isLoading} />
      ) : null}
      {tab === "risk" ? (
        <RiskPanel data={asRecord(riskQ.data)} loading={riskQ.isLoading} />
      ) : null}
      {tab === "supervisor" ? (
        <SupervisorPanel
          mode={mode}
          snapshot={supervisor}
          onSetMode={canChangeMode ? (m) => modeMut.mutate(m) : undefined}
          pending={modeMut.isPending}
        />
      ) : null}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="qf-caption text-[var(--fg-muted)]">{label}</div>
      <div className="font-mono text-[13px] tabular text-[var(--fg)]">
        {value || "—"}
      </div>
    </div>
  );
}

function MarketPanel({
  data,
  loading,
}: {
  data: Record<string, unknown>;
  loading: boolean;
}) {
  if (loading)
    return <p className="qf-caption">Loading market intelligence…</p>;
  const regime = asRecord(data.regime);
  const notes = asList(data.notes).map(String);
  return (
    <div className="grid gap-3">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Metric label="Symbol" value={str(data.symbol)} />
        <Metric label="Regime" value={str(regime.regime)} />
        <Metric label="Confidence" value={str(data.confidence)} />
        <Metric label="Model" value={str(data.model_version)} />
      </div>
      {notes.length ? (
        <p className="qf-caption text-[var(--fg-subtle)]">
          {notes.join(" · ")}
        </p>
      ) : null}
      <p className="qf-caption text-[var(--fg-muted)]">
        Sources: {asList(data.data_sources).map(String).join(", ") || "—"}
      </p>
    </div>
  );
}

function RegimePanel({
  data,
  loading,
}: {
  data: Record<string, unknown>;
  loading: boolean;
}) {
  if (loading) return <p className="qf-caption">Loading regime validation…</p>;
  const rows = asList(data.rows).map(asRecord);
  return (
    <div className="grid gap-2">
      <Metric
        label="Fixture agreement"
        value={`${str(data.agreement_count)}/${str(data.fixture_count)} (${str(data.agreement_rate)})`}
      />
      <p className="qf-caption text-[var(--fg-muted)]">
        Synthetic fixture agreement only — not live market accuracy.
      </p>
      <div className="max-h-40 overflow-auto">
        <table className="w-full text-left text-[12px]">
          <thead className="text-[var(--fg-muted)]">
            <tr>
              <th className="py-1">Label</th>
              <th className="py-1">Expected</th>
              <th className="py-1">Got</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-t border-[var(--border)]">
                <td className="py-1">{str(r.source_label)}</td>
                <td className="py-1 font-mono">{str(r.expected)}</td>
                <td className="py-1 font-mono">{str(r.got)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SignalPanel({
  data,
  loading,
}: {
  data: Record<string, unknown>;
  loading: boolean;
}) {
  if (loading) return <p className="qf-caption">Loading signal quality…</p>;
  return (
    <div className="grid gap-3">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Metric label="Quality" value={str(data.quality)} />
        <Metric label="Confidence" value={str(data.confidence)} />
        <Metric label="Regime" value={str(data.regime)} />
        <Metric label="Actionable" value={data.actionable ? "yes" : "no"} />
      </div>
      <p className="text-[12px] text-[var(--fg)]">{str(data.explanation)}</p>
      <p className="qf-caption text-[var(--fg-muted)]">
        {str(data.disclaimer)}
      </p>
    </div>
  );
}

function OptimizerPanel({
  data,
  loading,
}: {
  data: Record<string, unknown>;
  loading: boolean;
}) {
  if (loading) return <p className="qf-caption">Loading optimizer…</p>;
  const metrics = asRecord(data.metrics);
  return (
    <div className="grid gap-3">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Metric label="PF" value={str(metrics.profit_factor)} />
        <Metric label="Expectancy" value={str(metrics.expectancy)} />
        <Metric label="Max DD %" value={str(metrics.max_drawdown_pct)} />
        <Metric
          label="LIVE deploy"
          value={data.live_deploy_allowed ? "allowed" : "blocked"}
        />
      </div>
      <p className="qf-caption text-[var(--warning)]">
        {str(data.live_deploy_reason) || "Auto LIVE deploy forbidden"}
      </p>
    </div>
  );
}

function RiskPanel({
  data,
  loading,
}: {
  data: Record<string, unknown>;
  loading: boolean;
}) {
  if (loading) return <p className="qf-caption">Loading AI risk alerts…</p>;
  const alerts = asList(data.alerts).map(asRecord);
  if (!alerts.length) {
    return (
      <p className="qf-caption text-[var(--fg-muted)]">
        No alerts from supplied facts. Risk Center remains authoritative.
      </p>
    );
  }
  return (
    <ul className="grid gap-2">
      {alerts.map((a) => (
        <li
          key={str(a.code)}
          className="rounded border border-[var(--border)] px-2 py-1.5 text-[12px]"
        >
          <div className="font-medium text-[var(--fg)]">
            [{str(a.severity)}] {str(a.title)}
          </div>
          <div className="text-[var(--fg-muted)]">{str(a.explanation)}</div>
          <div className="qf-caption">
            Recommend: {str(a.recommended_action)}
          </div>
        </li>
      ))}
    </ul>
  );
}

function SupervisorPanel({
  mode,
  snapshot,
  onSetMode,
  pending,
}: {
  mode: string;
  snapshot: Record<string, unknown>;
  /** Absent for customers: the mode is platform-wide (owner/admin only). */
  onSetMode?: (mode: string) => void;
  pending: boolean;
}) {
  const modes = [
    "MONITOR_ONLY",
    "RECOMMENDATION",
    "APPROVAL_REQUIRED",
    "APPROVED_AUTOMATION",
  ];
  return (
    <div className="grid gap-3">
      <p className="qf-caption text-[var(--fg-muted)]">
        Default is MONITOR_ONLY. Automation never enables LIVE, raises risk, or
        disables safety.
      </p>
      {onSetMode ? (
        <div className="flex flex-wrap gap-2">
          {modes.map((m) => (
            <Button
              key={m}
              size="sm"
              variant={mode === m ? "default" : "secondary"}
              className="h-7 text-[11px]"
              disabled={pending}
              type="button"
              onClick={() => onSetMode(m)}
            >
              {m}
            </Button>
          ))}
        </div>
      ) : (
        <p className="qf-caption">Current mode: {mode}</p>
      )}
      <p className="qf-caption font-mono text-[var(--fg-subtle)]">
        allowed_auto=
        {asList(snapshot.allowed_auto_actions).map(String).join(",") || "—"}
      </p>
    </div>
  );
}
