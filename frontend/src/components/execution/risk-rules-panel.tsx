"use client";

import { memo, useMemo } from "react";
import { CheckCircle2, Circle, MinusCircle, ShieldAlert } from "lucide-react";
import { asList, asRecord, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

export type RiskRuleRow = {
  id: string;
  name: string;
  status: "pass" | "fail" | "n/a" | string;
  current: string;
  threshold: string;
  reason: string;
};

export function parseRiskRules(risk: Record<string, unknown> | null | undefined): RiskRuleRow[] {
  if (!risk) return [];
  const raw = asList(risk.rules);
  return raw
    .map((row) => {
      const r = asRecord(row);
      const id = str(r.id);
      if (!id) return null;
      return {
        id,
        name: str(r.name, id),
        status: str(r.status, "n/a").toLowerCase(),
        current: str(r.current, "—"),
        threshold: str(r.threshold, "—"),
        reason: str(r.reason),
      } satisfies RiskRuleRow;
    })
    .filter((r): r is RiskRuleRow => r != null);
}

export function formatRiskRejection(risk: Record<string, unknown> | null | undefined): string {
  if (!risk) return "Risk engine blocked execution";
  const reasons = asList(risk.reasons).map((r) => String(r)).filter(Boolean);
  const failed = parseRiskRules(risk).filter((r) => r.status === "fail");
  if (failed.length) {
    return failed
      .map((r) => `${r.name}: current ${r.current} / allowed ${r.threshold}`)
      .join(" · ");
  }
  if (reasons.length) return reasons.join(" · ");
  const warnings = asList(risk.warnings).map((r) => String(r)).filter(Boolean);
  if (warnings.length) return warnings.join(" · ");
  return `Risk ${str(risk.decision, "REJECT").toUpperCase()}`;
}

function StatusIcon({ status }: { status: string }) {
  if (status === "pass") {
    return <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--success)]" />;
  }
  if (status === "fail") {
    return <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--danger)]" />;
  }
  return <MinusCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--fg-subtle)]" />;
}

/** Institutional risk ledger — every engine rule with PASS/FAIL and values. */
export const RiskRulesPanel = memo(function RiskRulesPanel({
  risk,
  className,
}: {
  risk: Record<string, unknown> | null;
  className?: string;
}) {
  const rules = useMemo(() => parseRiskRules(risk), [risk]);
  const decision = str(risk?.decision, "").toUpperCase();
  const failed = rules.filter((r) => r.status === "fail");

  if (!risk) {
    return (
      <div
        className={cn(
          "rounded-lg border border-[var(--border)] bg-[var(--surface-2)]/70 px-3 py-2.5",
          className,
        )}
      >
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          Risk engine
        </p>
        <p className="mt-1.5 text-[11px] text-[var(--fg-muted)]">
          Awaiting risk check — rules appear after validate / safety / submit.
        </p>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "rounded-lg border border-[var(--border)] bg-[var(--surface-2)]/70 px-3 py-2.5",
        className,
      )}
      aria-live="polite"
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          Risk engine
        </p>
        <span
          className={cn(
            "text-[10px] font-medium uppercase tracking-wide",
            decision === "ALLOW"
              ? "text-[var(--success)]"
              : decision === "REDUCE_SIZE"
                ? "text-[var(--warning)]"
                : "text-[var(--danger)]",
          )}
        >
          {decision || "—"}
          {risk.risk_score != null ? ` · score ${String(risk.risk_score)}` : ""}
        </span>
      </div>

      {failed.length ? (
        <p className="mb-2 text-[11px] text-[var(--danger)]">
          Rejected by: {failed.map((r) => r.name).join(", ")}
        </p>
      ) : null}

      <ul className="max-h-56 space-y-1.5 overflow-y-auto pr-1">
        {rules.map((r) => (
          <li key={r.id} className="flex items-start gap-2 text-[11px]">
            <StatusIcon status={r.status} />
            <span className="min-w-0 flex-1">
              <span
                className={cn(
                  "font-medium",
                  r.status === "fail" ? "text-[var(--danger)]" : "text-[var(--fg)]",
                )}
              >
                {r.name}
              </span>
              <span className="mt-0.5 block font-mono text-[10px] text-[var(--fg-muted)]">
                Current {r.current}
                <span className="text-[var(--fg-subtle)]"> · </span>
                Allowed {r.threshold}
                <span className="ml-1 uppercase tracking-wide text-[var(--fg-subtle)]">
                  {r.status === "pass" ? "PASS" : r.status === "fail" ? "REJECT" : "N/A"}
                </span>
              </span>
              {r.reason ? (
                <span className="mt-0.5 block text-[10px] text-[var(--fg-subtle)]">{r.reason}</span>
              ) : null}
            </span>
          </li>
        ))}
        {!rules.length ? (
          <li className="flex items-start gap-2 text-[11px] text-[var(--fg-muted)]">
            <Circle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            {asList(risk.reasons).join(" · ") || "No rule breakdown in response"}
          </li>
        ) : null}
      </ul>
    </div>
  );
});
