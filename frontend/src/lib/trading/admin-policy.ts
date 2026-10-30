/** Build an owner policy save. A defer choice keeps the deployment flag. */

export type M1Choice = "defer" | "on" | "off";

export const POLICY_NUMERIC_KEYS = [
  "max_planned_risk_pct",
  "daily_loss_pct",
  "weekly_loss_pct",
  "max_drawdown_pct",
  "max_aggregate_open_risk_pct",
  "min_lot",
  "max_lot",
  "max_spread",
  "min_reward_risk",
  "min_trade_quality",
  "stop_atr_multiplier",
] as const;

export function m1ChoiceFromDocument(value: unknown): M1Choice {
  if (value === true) return "on";
  if (value === false) return "off";
  return "defer";
}

export function m1DocumentValue(choice: M1Choice): boolean | null {
  if (choice === "on") return true;
  if (choice === "off") return false;
  return null;
}

export function buildPolicyChanges(input: {
  draft: Record<string, string>;
  m1: M1Choice;
  m1Live: M1Choice;
}): Record<string, unknown> {
  const changes: Record<string, unknown> = {};
  for (const key of POLICY_NUMERIC_KEYS) {
    const raw = (input.draft[key] || "").trim();
    if (!raw) continue;
    changes[key] = key === "min_trade_quality" ? Number(raw) : raw;
  }
  changes.m1_micro_enabled = m1DocumentValue(input.m1);
  changes.m1_live_submit = m1DocumentValue(input.m1Live);
  changes.max_concurrent_positions = 1;
  changes.gold_only = true;
  changes.protective_stop_required = true;
  changes.evaluate_full_utc_day = true;
  changes.ite_enabled = true;
  changes.unified_decision_enabled = true;
  return changes;
}

export function policyStatusText(policy: {
  version?: number;
  source?: string;
  status?: string;
  applied_version?: number | null;
}): string {
  const version = policy.version ?? 0;
  const applied = policy.applied_version;
  if (policy.source === "approved_baseline" || version === 0) {
    return "No saved policy yet. The worker uses the approved baseline until you save.";
  }
  if (applied === version) {
    return `Saved version ${version} is applied by this worker.`;
  }
  return `Saved version ${version} is stored. The worker applies it on the next cycle.`;
}
