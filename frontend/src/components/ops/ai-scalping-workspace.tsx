"use client";

import { useQuery } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { iteReliabilityApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

function Panel({
  title,
  children,
  className,
}: {
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cn(
        "border border-[var(--border)] bg-[var(--surface)]",
        className,
      )}
    >
      <header className="border-b border-[var(--border)] px-3 py-2">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          {title}
        </h2>
      </header>
      <div className="p-3">{children}</div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-[var(--border)]/70 bg-[var(--bg)] px-3 py-2">
      <div className="text-[10px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
        {label}
      </div>
      <div className="mt-1 font-mono text-lg text-[var(--fg)]">{value}</div>
    </div>
  );
}

function fmt(v: unknown, digits = 2): string {
  if (v === null || v === undefined || v === "") return "—";
  const n = Number(v);
  if (Number.isFinite(n)) return n.toFixed(digits);
  return str(v, "—");
}

export function AiScalpingWorkspace() {
  const dash = useQuery({
    queryKey: ["ai-scalping-v5"],
    queryFn: iteReliabilityApi.aiScalping,
    retry: false,
    refetchInterval: 15_000,
  });

  if (dash.isLoading) return <DeskSkeleton rows={8} />;
  if (dash.isError) {
    return (
      <DeskError message="AI Scalping desk unavailable (OWNER/ADMIN · /ite/reliability/ai-scalping)." />
    );
  }

  const d = asRecord(dash.data);
  const setup = asRecord(d.current_setup);
  const safeguards = asRecord(d.safeguards);
  const diagnostics = asRecord(d.diagnostics);
  const summary = asRecord(diagnostics.summary);
  const recent = asList(diagnostics.recent).map(asRecord);
  const validation = asRecord(d.validation);
  const universe = asList(d.universe).map(String);
  const checks = asRecord(setup.quality_checks);

  const dir = str(setup.direction, "NONE").toUpperCase();
  const rejected = setup.reject === true;

  return (
    <div className="space-y-3">
      <Panel title="Mission">
        <p className="text-sm text-[var(--fg-muted)]">{str(d.mission)}</p>
        <div className="mt-2 flex flex-wrap gap-2">
          <Badge tone="success">risk={str(safeguards.risk_per_trade_pct)}%</Badge>
          <Badge tone="success">
            buy_only={String(safeguards.never_prefer_buy_only !== false)}
          </Badge>
          <Badge tone="success">
            martingale={String(safeguards.allow_martingale === true)}
          </Badge>
          <Badge tone="success">grid={String(safeguards.allow_grid === true)}</Badge>
        </div>
      </Panel>

      <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Direction" value={dir} />
        <Metric label="Confidence" value={fmt(setup.confidence, 0)} />
        <Metric label="Expected RR" value={fmt(setup.expected_rr, 2)} />
        <Metric label="Hold" value={str(setup.expected_hold_time, "—")} />
      </div>

      <Panel title="Current setup">
        <div className="mb-2 flex flex-wrap gap-2">
          <Badge tone={rejected ? "danger" : dir === "BUY" || dir === "SELL" ? "success" : "warning"}>
            {rejected ? "REJECTED" : dir}
          </Badge>
          <Badge tone="neutral">BUY {fmt(setup.buy_score, 0)}</Badge>
          <Badge tone="neutral">SELL {fmt(setup.sell_score, 0)}</Badge>
        </div>
        <p className="text-sm text-[var(--fg-muted)]">{str(setup.reason, "—")}</p>
        <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Metric label="Entry" value={str(setup.entry, "—")} />
          <Metric label="SL" value={str(setup.stop_loss, "—")} />
          <Metric label="TP" value={str(setup.take_profit, "—")} />
          <Metric label="Structure" value={fmt(setup.structure, 0)} />
          <Metric label="Momentum" value={fmt(setup.momentum, 0)} />
          <Metric label="Liquidity" value={fmt(setup.liquidity, 0)} />
        </div>
        {Object.keys(checks).length > 0 && (
          <ul className="mt-3 grid gap-1 text-xs sm:grid-cols-2">
            {Object.entries(checks).map(([k, v]) => (
              <li key={k} className="flex justify-between font-mono">
                <span>{k}</span>
                <Badge tone={v === true ? "success" : "danger"}>
                  {String(v)}
                </Badge>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <div className="grid gap-3 lg:grid-cols-2">
        <Panel title="Diagnostics">
          <div className="mb-2 flex gap-2">
            <Badge tone="success">taken {str(summary.taken, "0")}</Badge>
            <Badge tone="danger">rejected {str(summary.rejected, "0")}</Badge>
          </div>
          <ul className="max-h-56 space-y-1 overflow-auto text-xs">
            {recent.length === 0 ? (
              <li className="text-[var(--fg-subtle)]">No diagnostics yet.</li>
            ) : (
              recent.map((ev) => (
                <li
                  key={str(ev.id)}
                  className="border-b border-[var(--border)]/40 py-1"
                >
                  <span className="font-mono">
                    {str(ev.outcome)} · {str(ev.symbol)} · {str(ev.direction)}
                  </span>
                  <div className="text-[var(--fg-muted)]">{str(ev.reason)}</div>
                </li>
              ))
            )}
          </ul>
        </Panel>

        <Panel title="Validation (backtest vs live)">
          <p className="text-sm text-[var(--fg-muted)]">{str(validation.message)}</p>
          <Badge
            className="mt-2"
            tone={validation.recommend_deploy === true ? "success" : "warning"}
          >
            deploy={String(validation.recommend_deploy === true)}
          </Badge>
          <p className="mt-3 text-[10px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
            Universe
          </p>
          <div className="mt-1 flex flex-wrap gap-1">
            {universe.map((s) => (
              <Badge key={s} tone="neutral">
                {s}
              </Badge>
            ))}
          </div>
        </Panel>
      </div>
    </div>
  );
}
