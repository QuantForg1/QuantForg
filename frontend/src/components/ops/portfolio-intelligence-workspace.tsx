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

function Metric({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="border border-[var(--border)]/70 bg-[var(--bg)] px-3 py-2">
      <div className="text-[10px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
        {label}
      </div>
      <div className="mt-1 font-mono text-lg text-[var(--fg)]">{value}</div>
      {hint ? <div className="mt-0.5 text-[10px] text-[var(--fg-muted)]">{hint}</div> : null}
    </div>
  );
}

function fmt(v: unknown, digits = 2): string {
  if (v === null || v === undefined || v === "") return "—";
  const n = Number(v);
  if (Number.isFinite(n)) return n.toFixed(digits);
  return str(v, "—");
}

export function PortfolioIntelligenceWorkspace() {
  const dash = useQuery({
    queryKey: ["portfolio-intelligence-v9"],
    queryFn: iteReliabilityApi.portfolioIntelligence,
    retry: false,
    refetchInterval: 20_000,
  });

  if (dash.isLoading) return <DeskSkeleton rows={7} />;
  if (dash.isError) {
    return (
      <DeskError message="Portfolio Intelligence unavailable (OWNER/ADMIN · /ite/reliability/portfolio-intelligence)." />
    );
  }

  const d = asRecord(dash.data);
  const safeguards = asRecord(d.safeguards);
  const budget = asRecord(d.risk_budget);
  const alloc = asRecord(d.capital_allocation);
  const slices = asList(alloc.allocations).map(asRecord);
  const queue = asList(asRecord(d.opportunity_queue).items).map(asRecord);
  const regime = asRecord(d.market_regime);
  const stress = asRecord(d.stress_test);
  const scenarios = asList(stress.scenarios).map(asRecord);
  const protection = asRecord(d.capital_protection);
  const opt = asRecord(d.optimization);
  const exposure = asRecord(d.exposure_map);
  const corr = asRecord(d.correlation_matrix);
  const corrKeys = Object.keys(corr);
  const explanations = asList(d.explanations).map(asRecord);
  const recs = asList(d.recommendations).map(asRecord);
  const lt = asRecord(d.long_term_analytics);
  const r30 = asRecord(lt.rolling_30d);
  const r90 = asRecord(lt.rolling_90d);
  const r1y = asRecord(lt.rolling_1y);

  const health = str(d.portfolio_health, "—");

  return (
    <div className="space-y-3">
      <Panel title="Portfolio health">
        <div className="flex flex-wrap items-center gap-2">
          <Badge
            tone={
              health === "healthy"
                ? "success"
                : health === "protected"
                  ? "danger"
                  : "warning"
            }
          >
            {health}
          </Badge>
          <Badge tone="success">
            auto_reallocate={String(safeguards.auto_reallocate === true)}
          </Badge>
          <Badge tone="neutral">martingale=false · grid=false</Badge>
        </div>
      </Panel>

      <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Portfolio score" value={fmt(d.portfolio_score, 1)} />
        <Metric
          label="Risk budget"
          value={`${fmt(budget.risk_budget_pct, 2)}%`}
          hint={str(budget.reason)}
        />
        <Metric label="Expected return" value={fmt(d.expected_return, 3)} />
        <Metric label="Expected drawdown" value={`${fmt(d.expected_drawdown, 2)}%`} />
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <Panel title="Capital allocation">
          {slices.length === 0 ? (
            <p className="text-sm text-[var(--fg-muted)]">No ranked opportunities to allocate.</p>
          ) : (
            <div className="space-y-1 font-mono text-[11px]">
              {slices.map((s) => (
                <div
                  key={str(s.symbol)}
                  className="flex justify-between border-b border-[var(--border)]/40 py-1 last:border-0"
                >
                  <span>
                    #{str(s.rank)} {str(s.symbol)}
                  </span>
                  <span>{fmt(s.share_pct, 1)}%</span>
                </div>
              ))}
              <div className="pt-1 text-[var(--fg-muted)]">
                Reserve {fmt(alloc.reserve_pct, 0)}% · scale{" "}
                {fmt(alloc.new_exposure_scale, 2)} · auto_applied=false
              </div>
            </div>
          )}
        </Panel>

        <Panel title="Opportunity queue">
          {queue.length === 0 ? (
            <p className="text-sm text-[var(--fg-muted)]">Queue empty.</p>
          ) : (
            <div className="max-h-56 space-y-1 overflow-auto font-mono text-[11px]">
              {queue.map((q) => (
                <div
                  key={str(q.id)}
                  className="border-b border-[var(--border)]/40 py-1 last:border-0"
                >
                  P{str(q.priority)} {str(q.symbol)} {str(q.direction)} · conf{" "}
                  {str(q.confidence)} · RR {fmt(q.expected_rr, 2)} · impact{" "}
                  {fmt(q.estimated_portfolio_impact, 3)} · corr {fmt(q.correlation, 2)}
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>

      <div className="grid gap-3 lg:grid-cols-3">
        <Panel title="Market regime">
          <div className="font-mono text-sm">{str(regime.regime)}</div>
          <div className="mt-1 text-[11px] text-[var(--fg-muted)]">
            conf {str(regime.confidence)} · advisory
          </div>
          <div className="mt-2 text-[11px] text-[var(--fg-muted)]">
            {asList(regime.reasons).map(String).join(" · ") || "—"}
          </div>
        </Panel>

        <Panel title="Capital protection">
          <Metric
            label="Allow new"
            value={protection.allow_new_exposure === false ? "NO" : "YES"}
          />
          <Metric label="New scale" value={fmt(protection.new_exposure_scale, 2)} />
          <p className="mt-2 text-[11px] text-[var(--fg-muted)]">
            {asList(protection.reasons).map(String).join(" · ")}
          </p>
        </Panel>

        <Panel title="Long-term analytics">
          <div className="space-y-1 font-mono text-[11px]">
            <div>30d {fmt(r30.return_pct)}% · sharpe {fmt(r30.sharpe, 2)}</div>
            <div>90d {fmt(r90.return_pct)}% · stab {fmt(r90.stability, 1)}</div>
            <div>1y {fmt(r1y.return_pct)}% · eff {fmt(r1y.capital_efficiency, 2)}</div>
          </div>
        </Panel>
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <Panel title="Exposure map">
          {Object.keys(exposure).length === 0 ? (
            <p className="text-sm text-[var(--fg-muted)]">No open exposure.</p>
          ) : (
            <div className="font-mono text-[11px]">
              {Object.entries(exposure).map(([k, v]) => (
                <div key={k} className="flex justify-between">
                  <span>{k}</span>
                  <span>{fmt(v, 3)}</span>
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="Correlation matrix">
          {corrKeys.length === 0 ? (
            <p className="text-sm text-[var(--fg-muted)]">No matrix.</p>
          ) : (
            <div className="max-h-48 overflow-auto font-mono text-[10px]">
              <table className="w-full border-collapse">
                <thead>
                  <tr>
                    <th className="p-1 text-left" />
                    {corrKeys.slice(0, 6).map((k) => (
                      <th key={k} className="p-1 text-left">
                        {k.slice(0, 6)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {corrKeys.slice(0, 6).map((row) => (
                    <tr key={row}>
                      <td className="p-1">{row.slice(0, 6)}</td>
                      {corrKeys.slice(0, 6).map((col) => (
                        <td key={col} className="p-1">
                          {fmt(asRecord(corr[row])[col], 2)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      </div>

      <Panel title="Stress test">
        <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
          {scenarios.map((s) => (
            <div
              key={str(s.scenario)}
              className="border border-[var(--border)]/70 bg-[var(--bg)] px-2 py-2 font-mono text-[11px]"
            >
              <div className="uppercase text-[var(--fg-subtle)]">{str(s.scenario)}</div>
              <div className="mt-1">loss {fmt(s.estimated_loss_pct, 2)}%</div>
              <div className="text-[var(--fg-muted)]">{str(s.detail)}</div>
            </div>
          ))}
        </div>
        {stress.worst_case ? (
          <p className="mt-2 text-[11px] text-[var(--fg-muted)]">
            Worst: {str(asRecord(stress.worst_case).scenario)} ·{" "}
            {fmt(asRecord(stress.worst_case).estimated_loss_pct, 2)}%
          </p>
        ) : null}
      </Panel>

      <div className="grid gap-3 lg:grid-cols-2">
        <Panel title="Allocation explainability">
          {explanations.length === 0 ? (
            <p className="text-sm text-[var(--fg-muted)]">No explanations yet.</p>
          ) : (
            <div className="max-h-40 space-y-1 overflow-auto text-[11px]">
              {explanations.slice(0, 20).map((e) => (
                <div key={str(e.id)} className="border-b border-[var(--border)]/40 py-1 last:border-0">
                  {str(e.why)}
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="AI recommendations (advisory)">
          {recs.length === 0 ? (
            <p className="text-sm text-[var(--fg-muted)]">No recommendations.</p>
          ) : (
            <div className="max-h-40 space-y-1 overflow-auto text-[11px]">
              {recs.map((r) => (
                <div key={str(r.id)} className="border-b border-[var(--border)]/40 py-1 last:border-0">
                  <Badge tone="neutral">{str(r.kind)}</Badge> {str(r.message)}
                </div>
              ))}
            </div>
          )}
          <p className="mt-2 text-[10px] text-[var(--fg-muted)]">
            Optimizer corr {fmt(opt.correlation, 2)} · margin {fmt(opt.margin_usage, 3)} ·
            auto_applied=false
          </p>
        </Panel>
      </div>
    </div>
  );
}
