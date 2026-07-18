"use client";

import { memo } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { asList, asRecord, str } from "@/lib/desk";
import { cn } from "@/lib/utils";
import { ResearchEmpty } from "@/components/research/empty-state";

/**
 * Promote Gate — eligibility evaluate only. Deploy to Terminal is human-led.
 */
export const PromoteGate = memo(function PromoteGate({
  criteria,
  promoteResult,
  strategyKey,
  onEvaluate,
  evaluating,
  className,
}: {
  criteria: Record<string, unknown> | null;
  promoteResult: Record<string, unknown> | null;
  strategyKey: string;
  onEvaluate: () => void;
  evaluating: boolean;
  className?: string;
}) {
  const criteriaEntries = criteria
    ? Object.entries(criteria).slice(0, 10)
    : [];
  const eligible = Boolean(
    promoteResult &&
      (promoteResult.eligible_for_decision_engine ||
        promoteResult.eligible ||
        promoteResult.passed),
  );
  const checks = asList(
    promoteResult?.checks ?? promoteResult?.results ?? promoteResult?.criteria_results,
  ).map(asRecord);

  return (
    <section
      className={cn(
        "flex h-full min-h-0 flex-col rounded-md border border-[var(--border)] bg-[var(--surface)] p-3",
        className,
      )}
      aria-label="Promote to Terminal"
    >
      <header className="mb-2 flex shrink-0 items-center justify-between gap-2">
        <div>
          <h2 className="qf-label text-[var(--fg)]">Promote</h2>
          <p className="qf-caption">Eligibility only — never auto-deploys</p>
        </div>
        <div className="flex gap-1">
          <Button
            size="sm"
            className="h-7 text-[11px]"
            disabled={!strategyKey || evaluating}
            onClick={onEvaluate}
          >
            {evaluating ? "Evaluating…" : "Evaluate"}
          </Button>
          <Button size="sm" variant="secondary" className="h-7 text-[11px]" asChild>
            <Link href="/terminal">Terminal</Link>
          </Button>
          <Button size="sm" variant="ghost" className="h-7 text-[11px]" asChild>
            <Link href="/counsel">Counsel</Link>
          </Button>
        </div>
      </header>

      {!strategyKey ? (
        <ResearchEmpty
          title="Select a strategy"
          description="Promotion evaluate requires a strategy key from the library or catalog."
        />
      ) : (
        <div className="min-h-0 flex-1 space-y-3 overflow-y-auto text-[11px]">
          <p className="font-mono text-[var(--fg)]">{strategyKey}</p>

          {criteriaEntries.length > 0 ? (
            <div>
              <p className="mb-1 text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                Criteria
              </p>
              <ul className="space-y-1">
                {criteriaEntries.map(([k, v]) => (
                  <li key={k} className="flex justify-between gap-2">
                    <span className="text-[var(--fg-muted)]">{k}</span>
                    <span className="tabular text-[var(--fg)]">{String(v)}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="text-[var(--fg-subtle)]">No criteria payload loaded.</p>
          )}

          {promoteResult ? (
            <div>
              <p
                className={cn(
                  "font-medium",
                  eligible ? "text-[var(--success)]" : "text-[var(--warning)]",
                )}
              >
                {eligible
                  ? "Eligible for Decision Engine gate"
                  : str(
                      promoteResult.message,
                      "Not eligible — Decision Engine remains gatekeeper",
                    )}
              </p>
              {checks.length > 0 ? (
                <ul className="mt-2 space-y-1">
                  {checks.map((c, i) => (
                    <li key={i} className="flex justify-between gap-2 text-[var(--fg-muted)]">
                      <span>{str(c.name ?? c.criterion ?? c.id, `Check ${i + 1}`)}</span>
                      <span className="tabular">
                        {str(c.status ?? c.passed ?? c.result, "—")}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : (
            <p className="text-[var(--fg-subtle)]">
              Run Evaluate to call promotion/evaluate. Results are never fabricated.
            </p>
          )}
        </div>
      )}
    </section>
  );
});
