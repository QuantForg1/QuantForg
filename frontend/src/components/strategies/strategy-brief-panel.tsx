"use client";

import { useEffect, useState, createElement } from "react";
import { STRATEGY_BRIEFS } from "@/components/strategies/strategy-briefs";
import { strategyIconForKey } from "@/components/strategies/strategy-icons";
import { cn } from "@/lib/utils";

type DetailTab = "overview" | "parameters" | "rules" | "performance" | "backtest";

const TABS: { id: DetailTab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "parameters", label: "Parameters" },
  { id: "rules", label: "Rules" },
  { id: "performance", label: "Performance" },
  { id: "backtest", label: "Backtest" },
];

type StrategyEvaluation = {
  pending: boolean;
  error: string | null;
  result: Record<string, unknown> | null;
  onEvaluate: () => void;
};

type StrategyBriefPanelProps = {
  strategyKey: string;
  name: string;
  category: string;
  description: string;
  market: string;
  params: Record<string, unknown>;
  onServer: boolean;
  evaluation?: StrategyEvaluation;
};

function EvaluationResult({ result }: { result: Record<string, unknown> | null }) {
  if (!result) return null;
  if (result.ok === false) {
    const message = typeof result.error === "string" && result.error
      ? result.error
      : "The server could not evaluate this strategy.";
    return (
      <p role="status" className="text-sm leading-relaxed text-[var(--warning)]">
        Unavailable. {message}
      </p>
    );
  }
  const signal = result.signal && typeof result.signal === "object"
    ? (result.signal as Record<string, unknown>)
    : null;
  const action = typeof signal?.action === "string" ? signal.action : "";
  if (!action) {
    return (
      <p role="status" className="text-sm leading-relaxed text-[var(--fg-muted)]">
        The server returned no intention.
      </p>
    );
  }
  const confidence = typeof signal?.confidence === "number" && Number.isFinite(signal.confidence)
    ? signal.confidence
    : null;
  const reasons = Array.isArray(signal?.reasons)
    ? signal.reasons.filter((item): item is string => typeof item === "string" && item.length > 0)
    : [];
  return (
    <div role="status" className="grid gap-2 rounded-[var(--radius-sm)] border border-[var(--border)] p-3">
      <p className="text-sm font-semibold text-[var(--fg)]">
        Intention {action}
        {confidence !== null ? ` · ${Math.round(confidence * 100)}% confidence` : ""}
      </p>
      {reasons.length > 0 ? (
        <ul className="grid gap-1 text-sm leading-relaxed text-[var(--fg-muted)]">
          {reasons.slice(0, 4).map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-[var(--fg-muted)]">The server did not return a reason.</p>
      )}
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-3 text-sm">
      <span className="text-[var(--fg-muted)]">{label}</span>
      <span className="text-right font-medium text-[var(--fg)]">{value}</span>
    </div>
  );
}

export function StrategyBriefPanel({
  strategyKey,
  name,
  category,
  description,
  market,
  params,
  onServer,
  evaluation,
}: StrategyBriefPanelProps) {
  const [tab, setTab] = useState<DetailTab>("overview");
  useEffect(() => {
    setTab("overview");
  }, [strategyKey]);
  const brief = STRATEGY_BRIEFS[strategyKey];
  const title = name || strategyKey || "Strategy";
  const icon = strategyIconForKey(strategyKey);
  const categoryLabel = category ? category.replaceAll("_", " ") : "Not returned";
  const paramRows = Object.entries(params).filter(([, value]) => value !== undefined);

  return (
    <article
      id="strategy-detail"
      aria-live="polite"
      className="qf-overview-card h-full max-h-[calc(100dvh-6rem)] overflow-y-auto p-5 sm:p-6"
    >
      <div className="flex items-start gap-3">
        <span className="qf-overview-icon" aria-hidden>
          {createElement(icon, { className: "h-5 w-5" })}
        </span>
        <div className="min-w-0">
          <h2 className="text-lg font-semibold tracking-tight text-[var(--fg)]">{title}</h2>
          <p className="mt-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--accent)]">
            {categoryLabel}
            {market ? ` · ${market}` : ""}
          </p>
        </div>
      </div>
      <p className="mt-3 text-sm leading-relaxed text-[var(--fg-muted)]">
        {description || "No description was returned for this strategy."}
      </p>

      <div className="mt-4 flex gap-1 overflow-x-auto border-b border-[var(--border)]" role="tablist">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={tab === item.id}
            className={cn(
              "min-h-11 shrink-0 px-2.5 text-xs font-semibold",
              tab === item.id
                ? "border-b-2 border-[var(--accent)] text-[var(--accent)]"
                : "text-[var(--fg-muted)]",
            )}
            onClick={() => setTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="mt-4" role="tabpanel">
        {tab === "overview" ? (
          <div className="grid gap-4">
            <section>
              <h3 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
                Strategy info
              </h3>
              <div className="mt-2 grid gap-2">
                <InfoRow label="Type" value={categoryLabel} />
                <InfoRow label="Market" value={market || "—"} />
                <InfoRow label="Signal" value="Intention" />
              </div>
            </section>
            <section>
              <h3 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
                Key concept
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-[var(--fg)]">
                {brief?.concept || "A written concept was not supplied for this strategy."}
              </p>
            </section>
            <section>
              <h3 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
                What defines it
              </h3>
              {brief ? (
                <ul className="mt-2 space-y-2">
                  {brief.traits.map((trait) => (
                    <li key={trait} className="flex gap-2 text-sm leading-relaxed text-[var(--fg)]">
                      <span aria-hidden className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--accent)]" />
                      <span>{trait}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-2 text-sm text-[var(--fg-muted)]">No defining points were supplied.</p>
              )}
            </section>
          </div>
        ) : null}

        {tab === "parameters" ? (
          paramRows.length > 0 ? (
            <ul className="grid gap-2">
              {paramRows.map(([key, value]) => (
                <li
                  key={key}
                  className="flex items-start justify-between gap-3 rounded-[var(--radius-os)] border border-[var(--border)] px-3 py-2 text-sm"
                >
                  <span className="text-[var(--fg-muted)]">{key.replaceAll("_", " ")}</span>
                  <span className="max-w-[60%] break-words text-right font-medium text-[var(--fg)]">
                    {typeof value === "string" || typeof value === "number" || typeof value === "boolean"
                      ? String(value)
                      : "Structured value"}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm leading-relaxed text-[var(--fg-muted)]">No parameters were returned.</p>
          )
        ) : null}

        {tab === "rules" ? (
          <div className="grid gap-4">
            <section>
              <h3 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
                How it works
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-[var(--fg)]">
                {brief?.works || "No rule text was supplied for this strategy."}
              </p>
            </section>
            <section>
              <h3 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
                How it is used
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-[var(--fg)]">
                {brief?.usage || "No usage text was supplied for this strategy."}
              </p>
            </section>
          </div>
        ) : null}

        {tab === "performance" || tab === "backtest" ? (
          <p className="text-sm leading-relaxed text-[var(--fg-muted)]">
            No performance was returned for this strategy. Evaluate can show an intention when broker candles are available. It does not invent a win rate.
          </p>
        ) : null}
      </div>

      <p className="mt-4 text-xs leading-relaxed text-[var(--fg-subtle)]">
        {onServer
          ? "Evaluate returns an intention. It does not place an order, and the risk check can still turn that intention into hold."
          : "This strategy is in the engine. The connected server catalogue has not loaded it yet, so Evaluate on that server cannot run it."}
      </p>
      {onServer && evaluation ? (
        <div className="mt-4 grid gap-3">
          <button
            type="button"
            className="min-h-11 rounded-[var(--radius-sm)] bg-[var(--accent)] px-4 text-sm font-semibold text-[var(--accent-fg)] disabled:opacity-60"
            disabled={evaluation.pending}
            onClick={evaluation.onEvaluate}
          >
            {evaluation.pending ? "Evaluating…" : "Evaluate intention"}
          </button>
          {evaluation.error ? (
            <p role="alert" className="text-sm leading-relaxed text-[var(--danger)]">
              {evaluation.error}
            </p>
          ) : null}
          <EvaluationResult result={evaluation.result} />
        </div>
      ) : null}
    </article>
  );
}
