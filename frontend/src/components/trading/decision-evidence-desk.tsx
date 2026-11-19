"use client";

import { useState, type ReactNode } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Scale } from "lucide-react";
import { SignalsLockedView } from "@/components/billing/feature-locked";
import { DeskSkeleton } from "@/components/desk/primitives";
import { decisionEvidenceApi } from "@/lib/api/endpoints";
import { isSubscriptionRequiredError } from "@/lib/billing/feature-access";
import { asList, asRecord, str } from "@/lib/desk";
import {
  decisionTone,
  evidenceText,
  orderExecutionLabel,
} from "@/lib/trading/decision-evidence";
import { TRADING_SYMBOL } from "@/lib/trading/gold-only";
import { cn } from "@/lib/utils";

type Report = Record<string, unknown>;

function Card({
  title,
  children,
  className,
}: {
  title: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cn(
        "flex h-full min-h-[220px] flex-col rounded-2xl border border-[var(--border)] bg-[var(--surface)]",
        className,
      )}
    >
      <header className="border-b border-[var(--border)] px-4 py-3">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          {title}
        </h2>
      </header>
      <div className="flex flex-1 flex-col gap-3 p-4">{children}</div>
    </section>
  );
}

function Fact({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="grid grid-cols-1 gap-1 sm:grid-cols-[9.5rem_minmax(0,1fr)] sm:gap-3">
      <dt className="text-xs text-[var(--fg-muted)]">{label}</dt>
      <dd className="min-w-0 break-words text-sm text-[var(--fg)]">{evidenceText(value)}</dd>
    </div>
  );
}

function Lines({
  items,
  empty,
}: {
  items: string[];
  empty: string;
}) {
  if (items.length === 0) {
    return <p className="text-sm text-[var(--fg-muted)]">{empty}</p>;
  }
  return (
    <ul className="space-y-2">
      {items.map((item) => (
        <li key={item} className="break-words text-sm leading-relaxed text-[var(--fg)]">
          {item}
        </li>
      ))}
    </ul>
  );
}

function DecisionMark({ decision }: { decision: string }) {
  const tone = decisionTone(decision);
  return (
    <p
      className={cn(
        "inline-flex min-h-11 items-center justify-center rounded-full px-4 text-sm font-semibold tracking-wide",
        tone === "buy" && "bg-[var(--buy)] text-white",
        tone === "sell" && "bg-[var(--danger)] text-white",
        tone === "neutral" && "bg-[var(--surface-2)] text-[var(--fg)]",
      )}
    >
      {evidenceText(decision)}
    </p>
  );
}

export function DecisionEvidenceDesk() {
  const [historyIndex, setHistoryIndex] = useState<number | null>(null);
  const reportQ = useQuery({
    queryKey: ["decision-evidence", TRADING_SYMBOL],
    queryFn: () => decisionEvidenceApi.report(TRADING_SYMBOL),
    retry: false,
    staleTime: 15_000,
  });
  const historyQ = useQuery({
    queryKey: ["decision-evidence-history", TRADING_SYMBOL],
    queryFn: () => decisionEvidenceApi.history(TRADING_SYMBOL, 20),
    retry: false,
    staleTime: 30_000,
  });

  if (isSubscriptionRequiredError(reportQ.error) || isSubscriptionRequiredError(historyQ.error)) {
    return <SignalsLockedView />;
  }

  const live = asRecord(reportQ.data);
  const historyItems = asList(asRecord(historyQ.data).items);
  const selected =
    historyIndex != null && historyIndex >= 0 && historyIndex < historyItems.length
      ? historyItems[historyIndex]
      : null;
  const report = (selected ? asRecord(asRecord(selected).report) : live) as Report;
  const summary = asRecord(report.summary);
  const market = asRecord(report.market);
  const strategy = asRecord(report.strategy);
  const risk = asRecord(report.risk);
  const invalidation = asRecord(report.invalidation);
  const authorization = asRecord(report.authorization);
  const evidence = asList(report.evidence).map((item) => asRecord(item));
  const checks = asList(risk.checks).map((item) => asRecord(item));
  const missing = asList(risk.missing).map((item) => str(item)).filter(Boolean);
  const satisfied = asList(strategy.satisfied).map((item) => str(item)).filter(Boolean);
  const unsatisfied = asList(strategy.unsatisfied).map((item) => str(item)).filter(Boolean);
  const conditions = asList(invalidation.conditions).map((item) => asRecord(item));
  const awaiting = report.available === false || (!reportQ.data && !reportQ.isError);
  const decision = str(summary.decision, awaiting ? "Awaiting engine evidence" : "Not available");

  return (
    <div className="qf-desk min-w-0 space-y-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex min-w-0 items-start gap-3">
          <span className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[var(--accent-soft)] text-[var(--accent)]">
            <Scale className="h-5 w-5" aria-hidden />
          </span>
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--accent)]">
              Intelligence
            </p>
            <h1 className="text-[1.35rem] font-semibold leading-tight tracking-tight text-[var(--fg)] sm:text-[1.85rem]">
              Decision evidence
            </h1>
            <p className="mt-1 max-w-2xl text-sm leading-relaxed text-[var(--fg-muted)]">
              Explanation of the current engine decision, using only fields the platform already recorded.
              A BUY or SELL value is not proof that an order was executed.
            </p>
          </div>
        </div>
        <Link
          href="/signals"
          className="inline-flex h-11 items-center text-sm font-medium text-[var(--accent)] underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
        >
          Back to Signals
        </Link>
      </div>

      {report.test_synthetic === true ? (
        <p className="rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-4 py-3 text-sm text-[var(--fg)]">
          This record is marked TEST/SYNTHETIC. It is not production evidence.
        </p>
      ) : null}
      {report.stale === true ? (
        <p className="rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-4 py-3 text-sm text-[var(--fg)]">
          Market data on this decision is stale.
        </p>
      ) : null}
      {reportQ.isError && !reportQ.data ? (
        <p className="rounded-xl border border-[var(--border)] bg-[var(--surface)] px-4 py-3 text-sm text-[var(--fg-muted)]">
          Decision evidence could not be loaded. Not available.
        </p>
      ) : null}

      <div className="grid grid-cols-1 items-start gap-4 xl:grid-cols-[minmax(0,1fr)_17rem]">
        <div className="grid grid-cols-1 items-stretch gap-4 lg:grid-cols-2">
          {reportQ.isLoading && !reportQ.data ? (
            <div className="lg:col-span-2">
              <DeskSkeleton />
            </div>
          ) : (
            <>
              <Card title="Decision summary" className="lg:col-span-2">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <DecisionMark decision={decision} />
                  <p className="text-xs text-[var(--fg-muted)]">
                    {historyIndex != null ? "History record" : "Current signal record"}
                  </p>
                </div>
                {awaiting && historyIndex == null ? (
                  <p className="text-sm text-[var(--fg-muted)]">Awaiting engine evidence</p>
                ) : null}
                {historyIndex != null && str(report.history_note, "") ? (
                  <p className="text-sm leading-relaxed text-[var(--fg-muted)]">
                    {str(report.history_note)}
                  </p>
                ) : null}
                <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <Fact label="Instrument" value={summary.symbol} />
                  <Fact label="Strategy" value={summary.strategy} />
                  <Fact label="Timestamp" value={summary.timestamp} />
                  <Fact label="Source engine" value={summary.source_engine} />
                  <Fact label="Status" value={summary.status} />
                  <Fact label="Signal id" value={summary.signal_id} />
                </dl>
              </Card>

              <Card title="Market context">
                {market.available === false ? (
                  <p className="text-sm text-[var(--fg-muted)]">
                    {str(market.empty_reason, "Not available")}
                  </p>
                ) : (
                  <dl className="space-y-3">
                    <Fact label="Data state" value={market.data_state} />
                    <Fact label="Freshness time" value={market.timestamp} />
                    <Fact label="Timeframe" value={market.timeframe} />
                    <Fact label="Trend" value={market.trend} />
                    <Fact label="Volatility" value={market.volatility} />
                    <Fact label="Structure" value={market.structure} />
                    <Fact label="ATR" value={market.atr} />
                    <Fact label="Spread" value={market.spread} />
                    <Fact label="Session" value={market.session} />
                    <Fact label="Price" value={market.price} />
                  </dl>
                )}
              </Card>

              <Card title="Strategy reasoning">
                {strategy.available === false ? (
                  <p className="text-sm text-[var(--fg-muted)]">Awaiting engine evidence</p>
                ) : (
                  <>
                    <dl className="space-y-3">
                      <Fact label="Strategy" value={strategy.strategy} />
                      <Fact label="Engine" value={strategy.engine} />
                      <Fact label="Reason" value={strategy.reason} />
                    </dl>
                    <div>
                      <p className="mb-2 text-xs font-medium uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                        Conditions satisfied
                      </p>
                      <Lines items={satisfied} empty="Not available" />
                    </div>
                    <div>
                      <p className="mb-2 text-xs font-medium uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                        Conditions not satisfied
                      </p>
                      <Lines items={unsatisfied} empty="Not available" />
                    </div>
                  </>
                )}
              </Card>

              <Card title="Risk assessment">
                <p className="text-sm leading-relaxed text-[var(--fg-muted)]">
                  {str(
                    risk.note,
                    "Risk values are copied from the signal record. This report does not calculate or replace a risk value.",
                  )}
                </p>
                {checks.length === 0 ? (
                  <p className="text-sm text-[var(--fg-muted)]">Not available</p>
                ) : (
                  <ul className="space-y-2">
                    {checks.map((check) => (
                      <li
                        key={`${str(check.name)}-${str(check.state)}`}
                        className="flex flex-wrap items-baseline justify-between gap-2 border-b border-[var(--border)] pb-2 text-sm"
                      >
                        <span className="text-[var(--fg)]">{evidenceText(check.name)}</span>
                        <span className="font-mono text-xs text-[var(--fg-muted)]">
                          {evidenceText(check.state)}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
                <Fact label="Recorded risk field" value={risk.recorded_limit} />
                <div>
                  <p className="mb-2 text-xs font-medium uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                    Missing risk information
                  </p>
                  <Lines items={missing} empty="Not available" />
                </div>
              </Card>

              <Card title="Invalidation">
                {invalidation.available === false || conditions.length === 0 ? (
                  <p className="text-sm text-[var(--fg-muted)]">
                    {str(invalidation.empty_reason, "Not available")}
                  </p>
                ) : (
                  <ul className="space-y-3">
                    {conditions.map((condition) => (
                      <li key={`${str(condition.label)}-${str(condition.value)}`} className="text-sm">
                        <p className="text-[var(--fg)]">{evidenceText(condition.label)}</p>
                        <p className="mt-1 break-words text-[var(--fg-muted)]">
                          {evidenceText(condition.value)}
                        </p>
                        <p className="mt-1 text-xs text-[var(--fg-subtle)]">
                          {evidenceText(condition.source)}
                        </p>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>

              <Card title="Execution authorization" className="lg:col-span-2">
                <p className="text-sm leading-relaxed text-[var(--fg-muted)]">
                  {str(
                    authorization.note,
                    "A BUY or SELL value is not proof that an order was executed.",
                  )}
                </p>
                <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <Fact label="Research decision" value={authorization.research_decision} />
                  <Fact label="Strategy evaluation" value={authorization.strategy_evaluation} />
                  <Fact label="Risk approval" value={authorization.risk_approval} />
                  <Fact label="Execution authorization" value={authorization.execution_authorization} />
                  <Fact label="Live trading state" value={authorization.live_trading_state} />
                  <Fact
                    label="Order"
                    value={orderExecutionLabel({
                      orderExecuted: authorization.order_executed,
                      orderSent: authorization.order_sent,
                    })}
                  />
                  <Fact label="Lifecycle" value={authorization.execution_lifecycle} />
                  <Fact label="Ticket" value={authorization.ticket} />
                </dl>
              </Card>

              <Card title="Decision evidence" className="lg:col-span-2">
                {evidence.length === 0 ? (
                  <p className="text-sm text-[var(--fg-muted)]">Awaiting engine evidence</p>
                ) : (
                  <ul className="divide-y divide-[var(--border)]">
                    {evidence.map((item) => (
                      <li
                        key={`${str(item.source)}-${str(item.label)}`}
                        className="grid grid-cols-1 gap-1 py-3 sm:grid-cols-[10rem_minmax(0,1fr)] sm:gap-3"
                      >
                        <p className="text-xs text-[var(--fg-muted)]">{evidenceText(item.label)}</p>
                        <div className="min-w-0">
                          <p className="break-words text-sm text-[var(--fg)]">{evidenceText(item.value)}</p>
                          <p className="mt-1 break-words text-xs text-[var(--fg-subtle)]">
                            {evidenceText(item.source)} · {evidenceText(item.engine)} ·{" "}
                            {evidenceText(item.timestamp)}
                          </p>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            </>
          )}
        </div>

        <aside className="flex min-h-[220px] flex-col rounded-2xl border border-[var(--border)] bg-[var(--surface)]">
          <header className="border-b border-[var(--border)] px-4 py-3">
            <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
              Decision history
            </h2>
          </header>
          <div className="flex flex-1 flex-col gap-2 p-3">
            <button
              type="button"
              onClick={() => setHistoryIndex(null)}
              className={cn(
                "rounded-xl px-3 py-2 text-left text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]",
                historyIndex == null
                  ? "bg-[var(--accent-soft)] text-[var(--fg)]"
                  : "text-[var(--fg-muted)] hover:bg-[var(--surface-2)]",
              )}
            >
              Current decision
            </button>
            {historyQ.isLoading ? (
              <p className="px-3 py-2 text-sm text-[var(--fg-muted)]">Loading history…</p>
            ) : null}
            {!historyQ.isLoading && historyItems.length === 0 ? (
              <p className="px-3 py-2 text-sm text-[var(--fg-muted)]">
                {historyQ.isError ? "Not available" : "Awaiting engine evidence"}
              </p>
            ) : null}
            <ul className="space-y-1">
              {historyItems.map((item, index) => {
                const row = asRecord(item);
                const key = `${index}|${str(row.symbol)}|${str(row.timestamp)}|${str(row.decision)}`;
                return (
                  <li key={key}>
                    <button
                      type="button"
                      onClick={() => setHistoryIndex(index)}
                      className={cn(
                        "w-full rounded-xl px-3 py-2 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]",
                        historyIndex === index
                          ? "bg-[var(--accent-soft)]"
                          : "hover:bg-[var(--surface-2)]",
                      )}
                    >
                      <span className="block text-sm font-medium text-[var(--fg)]">
                        {evidenceText(row.symbol)} · {evidenceText(row.decision)}
                      </span>
                      <span className="mt-0.5 block text-xs text-[var(--fg-muted)]">
                        {evidenceText(row.timestamp)}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        </aside>
      </div>
    </div>
  );
}
