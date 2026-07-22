"use client";

import { useQuery } from "@tanstack/react-query";
import { ClipboardCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { tradingOperationsCenterApi } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { formatNumber } from "@/lib/utils";

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-[var(--border)] bg-[var(--bg)]/40 px-2.5 py-2">
      <p className="text-[9px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
        {label}
      </p>
      <p className="mt-1 font-mono text-sm tabular text-[var(--fg)]">{value}</p>
    </div>
  );
}

function fmt(v: unknown, d = 2): string {
  const n = num(v);
  return Number.isFinite(n) ? formatNumber(n, d) : "—";
}

function fmtPct(v: unknown): string {
  const n = num(v);
  return Number.isFinite(n) ? `${formatNumber(n * 100, 1)}%` : "—";
}

/**
 * Institutional Trading Operations Center — advisory only.
 * Never modifies strategy / risk / safety / execution / Performance IQ / Evidence Lab.
 */
export function TradingOperationsCenterWorkspace() {
  const q = useQuery({
    queryKey: ["trading-operations-center"],
    queryFn: () => tradingOperationsCenterApi.dashboard(),
    retry: false,
    staleTime: 15_000,
  });

  if (q.isLoading && !q.data) return <DeskSkeleton rows={10} />;
  if (q.isError) {
    return (
      <DeskError
        message="Trading Operations Center unavailable."
        onRetry={() => void q.refetch()}
      />
    );
  }

  const d = asRecord(q.data);
  const brief = asRecord(d.daily_brief);
  const checklist = asRecord(d.checklist);
  const items = asList(checklist.items).map(asRecord);
  const failures = asList(checklist.failures).map(asRecord);
  const eod = asRecord(d.end_of_day);
  const weekly = asRecord(d.weekly_review);
  const monthly = asRecord(d.monthly_review);
  const alerts = asRecord(d.operational_alerts);
  const alertRows = asList(alerts.alerts).map(asRecord);
  const exec = asRecord(d.executive_dashboard);
  const recs = asList(d.recommendations).map(String);
  const news = asList(asRecord(brief.high_impact_news).items).map(asRecord);
  const sessions = asList(brief.expected_sessions).map(String);

  if (str(d.status) === "unavailable") {
    return (
      <DeskEmpty
        icon={ClipboardCheck}
        title="Operations Center empty"
        description="Supply ops facts and journals, or run scripts/trading_operations_center.py --demo."
      />
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2 border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Trading Operations Center
          </span>
          <Badge tone="neutral">v{str(d.version, "1.0.1")}</Badge>
          <Badge tone={checklist.all_passed ? "success" : "warning"}>
            checklist {checklist.all_passed ? "READY" : "BLOCKED"}
          </Badge>
          <Badge tone="neutral">
            alerts={str(alerts.alert_count, "0")}
          </Badge>
        </div>
      </div>

      <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
          Executive dashboard
        </h3>
        <div className="mt-2 grid grid-cols-2 gap-2 md:grid-cols-3 lg:grid-cols-6">
          <Stat
            label="Ops"
            value={`${str(asRecord(exec.operations_status).passed_count, "0")}/${str(asRecord(exec.operations_status).total, "0")}`}
          />
          <Stat
            label="Trades"
            value={str(asRecord(exec.performance).trades, "—")}
          />
          <Stat
            label="Win rate"
            value={fmtPct(asRecord(exec.performance).win_rate)}
          />
          <Stat
            label="Evidence replay"
            value={str(asRecord(exec.evidence).replay_opportunities, "—")}
          />
          <Stat
            label="Confidence"
            value={str(asRecord(exec.confidence).overall, "—")}
          />
          <Stat
            label="Alerts"
            value={str(exec.open_alert_count, "0")}
          />
        </div>
      </section>

      <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
          Daily brief · {str(brief.trading_date, "—")}
        </h3>
        <p className="mt-1 text-[12px] text-[var(--fg)]">
          Sessions: {sessions.length ? sessions.join(" · ") : "—"} · Regime:{" "}
          {str(brief.current_market_regime, "—")} · Vol:{" "}
          {str(brief.volatility_expectation, "—")}
        </p>
        {news.length > 0 ? (
          <ul className="mt-2 list-disc space-y-1 pl-4 text-[12px]">
            {news.map((n, i) => (
              <li key={`${str(n.title)}-${i}`}>
                {str(n.title)} ({str(n.impact, "n/a")})
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-[11px] text-[var(--fg-subtle)]">
            {str(asRecord(brief.high_impact_news).note, "No high-impact news")}
          </p>
        )}
      </section>

      <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
          Daily operations checklist
        </h3>
        <ul className="mt-2 space-y-1">
          {items.map((item) => (
            <li
              key={str(item.key)}
              className="border border-[var(--border)] bg-[var(--bg)]/40 px-2.5 py-1.5 text-[12px]"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span>
                  {item.passed ? "☑" : "☐"} {str(item.label)}
                </span>
                <span className="font-mono text-[10px] text-[var(--fg-subtle)]">
                  {str(item.value)} · {str(item.status)}
                </span>
              </div>
              {!item.passed ? (
                <div className="mt-1 space-y-0.5 text-[11px] text-[var(--fg-subtle)]">
                  <p>
                    <span className="uppercase tracking-wide">Why:</span>{" "}
                    {str(item.why)}
                  </p>
                  <p>
                    <span className="uppercase tracking-wide">Resolution:</span>{" "}
                    {str(item.how_to_resolve)}
                  </p>
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      </section>

      <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
          End-of-day
        </h3>
        <div className="mt-2 grid grid-cols-2 gap-2 md:grid-cols-5">
          <Stat label="Trades" value={str(eod.trades, "—")} />
          <Stat label="Win rate" value={fmtPct(eod.win_rate)} />
          <Stat label="PF" value={fmt(eod.profit_factor)} />
          <Stat label="Expectancy" value={fmt(eod.expectancy)} />
          <Stat label="DD%" value={fmt(eod.drawdown)} />
        </div>
      </section>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
          <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
            Weekly review
          </h3>
          <p className="mt-2 text-[11px] font-semibold text-[var(--fg)]">Improvements</p>
          <ul className="mt-1 list-disc space-y-1 pl-4 text-[12px]">
            {asList(weekly.improvements).length
              ? asList(weekly.improvements).map(String).map((x) => <li key={x}>{x}</li>)
              : <li className="text-[var(--fg-subtle)]">None flagged</li>}
          </ul>
          <p className="mt-2 text-[11px] font-semibold text-[var(--fg)]">Regressions</p>
          <ul className="mt-1 list-disc space-y-1 pl-4 text-[12px]">
            {asList(weekly.regressions).length
              ? asList(weekly.regressions).map(String).map((x) => <li key={x}>{x}</li>)
              : <li className="text-[var(--fg-subtle)]">None flagged</li>}
          </ul>
          <p className="mt-2 text-[11px] font-semibold text-[var(--fg)]">Unknowns</p>
          <ul className="mt-1 list-disc space-y-1 pl-4 text-[12px]">
            {asList(weekly.unknowns).map(String).map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
        </section>

        <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
          <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
            Monthly review
          </h3>
          <div className="mt-2 grid grid-cols-2 gap-2">
            <Stat
              label="WR"
              value={fmtPct(asRecord(monthly.performance).win_rate)}
            />
            <Stat
              label="Confidence"
              value={str(asRecord(monthly.confidence_growth).overall_confidence, "—")}
            />
          </div>
          <p className="mt-2 text-[11px] font-semibold text-[var(--fg)]">
            Open research topics
          </p>
          <ul className="mt-1 list-disc space-y-1 pl-4 text-[12px]">
            {asList(monthly.open_research_topics).map(String).map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
        </section>
      </div>

      <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
          Operational alerts
        </h3>
        {alertRows.length === 0 ? (
          <p className="mt-2 text-[12px] text-[var(--fg-subtle)]">No ops alerts.</p>
        ) : (
          <ul className="mt-2 space-y-1">
            {alertRows.map((a) => (
              <li
                key={str(a.code)}
                className="border border-[var(--border)] bg-[var(--bg)]/40 px-2.5 py-1.5 text-[12px]"
              >
                <span className="font-semibold uppercase tracking-wide text-[var(--fg-subtle)]">
                  {str(a.severity)}
                </span>{" "}
                {str(a.title)} — {str(a.detail)}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
          Outstanding actions
        </h3>
        <ul className="mt-2 list-disc space-y-1 pl-4 text-[12px]">
          {(failures.length
            ? failures.map(
                (f) => `Resolve ${str(f.label)}: ${str(f.how_to_resolve)}`,
              )
            : recs
          ).map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
        <p className="mt-2 text-[10px] text-[var(--fg-subtle)]">
          Recommendations are operational only — never strategy changes.
        </p>
      </section>
    </div>
  );
}
