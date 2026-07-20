"use client";

import { memo, useMemo } from "react";
import { AlertTriangle, CheckCircle2, MinusCircle, ShieldAlert } from "lucide-react";
import { asList, asRecord, num, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

export type RiskRuleRow = {
  id: string;
  name: string;
  status: "pass" | "warn" | "fail" | "n/a" | string;
  current: string;
  threshold: string;
  reason: string;
  suggested_action: string;
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
        current: str(r.current, "Not available"),
        threshold: str(r.threshold, "Not available"),
        reason: str(r.reason),
        suggested_action: str(r.suggested_action),
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

function statusLabel(status: string): string {
  if (status === "pass") return "PASS";
  if (status === "warn") return "WARN";
  if (status === "fail") return "FAIL";
  return "N/A";
}

function StatusIcon({ status }: { status: string }) {
  if (status === "pass") {
    return <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--success)]" />;
  }
  if (status === "warn") {
    return <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--warning)]" />;
  }
  if (status === "fail") {
    return <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--danger)]" />;
  }
  return <MinusCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--fg-subtle)]" />;
}

/** Institutional Risk Center — every engine rule with PASS/WARN/FAIL + actions. */
export const RiskRulesPanel = memo(function RiskRulesPanel({
  risk,
  className,
}: {
  risk: Record<string, unknown> | null;
  className?: string;
}) {
  const rules = useMemo(() => parseRiskRules(risk), [risk]);
  const decision = str(risk?.decision, "").toUpperCase();
  const pressure = num(risk?.risk_score, NaN);
  const health = Number.isFinite(pressure) ? Math.max(0, Math.min(100, 100 - pressure)) : null;
  const failed = rules.filter((r) => r.status === "fail");
  const warned = rules.filter((r) => r.status === "warn");

  const healthTone =
    health == null
      ? "text-[var(--fg-muted)]"
      : health >= 70
        ? "text-[var(--success)]"
        : health >= 40
          ? "text-[var(--warning)]"
          : "text-[var(--danger)]";

  const healthBar =
    health == null
      ? "bg-[var(--fg-subtle)]"
      : health >= 70
        ? "bg-[var(--success)]"
        : health >= 40
          ? "bg-[var(--warning)]"
          : "bg-[var(--danger)]";

  if (!risk) {
    return (
      <div
        className={cn(
          "rounded-lg border border-[var(--border)] bg-[var(--surface-2)] px-3 py-3",
          className,
        )}
      >
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          Institutional Risk Center
        </p>
        <p className="mt-2 text-[11px] text-[var(--fg-muted)]">
          Awaiting live risk check — rules populate after validate / safety / submit. No mock
          values.
        </p>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "rounded-lg border border-[var(--border)] bg-[var(--surface-2)] px-3 py-3",
        className,
      )}
      aria-live="polite"
    >
      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Institutional Risk Center
          </p>
          <p className="mt-1 text-[11px] text-[var(--fg-muted)]">
            Decision{" "}
            <span
              className={cn(
                "font-medium uppercase",
                decision === "ALLOW"
                  ? "text-[var(--success)]"
                  : decision === "REDUCE_SIZE"
                    ? "text-[var(--warning)]"
                    : "text-[var(--danger)]",
              )}
            >
              {decision || "—"}
            </span>
            {str(risk.risk_band) ? ` · band ${str(risk.risk_band)}` : ""}
          </p>
        </div>
        <div className="min-w-[7.5rem] text-right">
          <p className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
            Overall risk health
          </p>
          <p className={cn("font-mono text-2xl tabular-nums leading-none", healthTone)}>
            {health == null ? "—" : `${Math.round(health)}`}
            <span className="text-sm text-[var(--fg-subtle)]"> /100</span>
          </p>
          <div className="mt-1.5 h-1 overflow-hidden rounded bg-[var(--bg-elevated)]">
            <div
              className={cn("h-full transition-[width] duration-[var(--duration-os)]", healthBar)}
              style={{ width: `${health ?? 0}%` }}
            />
          </div>
        </div>
      </div>

      {failed.length ? (
        <p className="mb-2 text-[11px] text-[var(--danger)]">
          FAIL: {failed.map((r) => r.name).join(", ")}
        </p>
      ) : null}
      {warned.length ? (
        <p className="mb-2 text-[11px] text-[var(--warning)]">
          WARN: {warned.map((r) => r.name).join(", ")}
        </p>
      ) : null}

      <div className="max-h-72 overflow-y-auto pr-1">
        <table className="w-full border-collapse text-left text-[11px]">
          <thead className="sticky top-0 bg-[var(--surface-2)] text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
            <tr>
              <th className="py-1.5 pr-2 font-medium">Rule</th>
              <th className="py-1.5 pr-2 font-medium">Status</th>
              <th className="py-1.5 pr-2 font-medium">Current</th>
              <th className="py-1.5 pr-2 font-medium">Threshold</th>
              <th className="py-1.5 font-medium">Action</th>
            </tr>
          </thead>
          <tbody>
            {rules.map((r) => (
              <tr key={r.id} className="border-t border-[var(--border)]/60 align-top">
                <td className="py-2 pr-2">
                  <div className="flex items-start gap-1.5">
                    <StatusIcon status={r.status} />
                    <div>
                      <p
                        className={cn(
                          "font-medium",
                          r.status === "fail"
                            ? "text-[var(--danger)]"
                            : r.status === "warn"
                              ? "text-[var(--warning)]"
                              : "text-[var(--fg)]",
                        )}
                      >
                        {r.name}
                      </p>
                      {r.reason ? (
                        <p className="mt-0.5 text-[10px] text-[var(--fg-subtle)]">{r.reason}</p>
                      ) : null}
                    </div>
                  </div>
                </td>
                <td
                  className={cn(
                    "py-2 pr-2 font-mono text-[10px] uppercase",
                    r.status === "fail"
                      ? "text-[var(--danger)]"
                      : r.status === "warn"
                        ? "text-[var(--warning)]"
                        : r.status === "pass"
                          ? "text-[var(--success)]"
                          : "text-[var(--fg-subtle)]",
                  )}
                >
                  {statusLabel(r.status)}
                </td>
                <td className="py-2 pr-2 font-mono tabular-nums text-[var(--fg-muted)]">
                  {r.current || "Not available"}
                </td>
                <td className="py-2 pr-2 font-mono tabular-nums text-[var(--fg-muted)]">
                  {r.threshold || "Not available"}
                </td>
                <td className="py-2 text-[10px] text-[var(--fg-subtle)]">
                  {r.suggested_action || "Not available"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rules.length ? (
          <p className="py-3 text-[11px] text-[var(--fg-muted)]">
            {asList(risk.reasons).join(" · ") || "Not available"}
          </p>
        ) : null}
      </div>
    </div>
  );
});
