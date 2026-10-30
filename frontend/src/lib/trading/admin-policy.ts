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

export const ACTIVE_RISK_CEILING = 14;
export const ACTIVE_QUALITY_FLOOR = 70;
export const ACTIVE_REWARD_RISK_FLOOR = 1.5;
export const EXPERIMENTAL_REWARD_RISK = [0.1, 0.15, 0.2] as const;

export const EXPERIMENTAL_KEYS = [
  "max_planned_risk_pct",
  "max_aggregate_open_risk_pct",
  "daily_loss_pct",
  "max_lot",
  "max_spread",
  "min_reward_risk",
  "min_trade_quality",
  "stop_atr_multiplier",
  "max_concurrent_positions",
] as const;

/** Draft only. Saving this object does not promote it or load the worker. */
export const EXPERIMENT_DEFAULTS: Record<(typeof EXPERIMENTAL_KEYS)[number], string> = {
  max_planned_risk_pct: "14",
  max_aggregate_open_risk_pct: "14",
  daily_loss_pct: "19",
  max_lot: "0.01",
  max_spread: "0.45",
  min_reward_risk: "0.20",
  min_trade_quality: "70",
  stop_atr_multiplier: "1.00",
  max_concurrent_positions: "1",
};

function numeric(raw: string): number | null {
  if (!raw.trim()) return null;
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

export function validateActiveDraft(draft: Record<string, string>): string[] {
  const errors: string[] = [];
  const risk = numeric(draft.max_planned_risk_pct || "");
  const aggregate = numeric(draft.max_aggregate_open_risk_pct || "");
  const quality = numeric(draft.min_trade_quality || "");
  const reward = numeric(draft.min_reward_risk || "");
  if (risk != null && (risk <= 0 || risk > ACTIVE_RISK_CEILING)) {
    errors.push(`Planned risk ceiling is ${ACTIVE_RISK_CEILING}%, not 9%.`);
  }
  if (aggregate != null && (aggregate <= 0 || aggregate > ACTIVE_RISK_CEILING)) {
    errors.push(`Aggregate open-risk ceiling is ${ACTIVE_RISK_CEILING}%, not 9%.`);
  }
  if (quality != null && (quality < ACTIVE_QUALITY_FLOOR || quality > 100)) {
    errors.push(`Minimum trade quality is ${ACTIVE_QUALITY_FLOOR} to 100, not 75.`);
  }
  if (reward != null && reward < ACTIVE_REWARD_RISK_FLOOR) {
    errors.push(
      "Active minimum reward/risk stays 1.50. Candidates 0.10, 0.15, and 0.20 are experimental and are not activated by this save.",
    );
  }
  return errors;
}

export function validateExperimentalDraft(draft: Record<string, string>): string[] {
  const errors = validateActiveDraft({
    ...draft,
    min_reward_risk: "",
  }).filter((item) => !item.startsWith("Active minimum"));
  const reward = numeric(draft.min_reward_risk || "");
  if (reward == null) {
    errors.push("Experimental reward/risk is required.");
  } else if (!EXPERIMENTAL_REWARD_RISK.some((item) => Math.abs(item - reward) < 1e-9)) {
    errors.push("Experimental reward/risk must be 0.10, 0.15, or 0.20.");
  }
  return errors;
}

export function buildExperimentalChanges(
  draft: Record<string, string>,
): Record<string, unknown> {
  const experimental: Record<string, unknown> = {};
  for (const key of EXPERIMENTAL_KEYS) {
    const raw = (draft[key] || "").trim();
    if (!raw) continue;
    experimental[key] = key === "min_trade_quality" || key === "max_concurrent_positions"
      ? Number(raw)
      : raw;
  }
  return { experimental };
}

export function policyStatusText(policy: {
  version?: number;
  source?: string;
  status?: string;
  applied_version?: number | null;
  worker_confirmed?: boolean;
}): string {
  const version = policy.version ?? 0;
  const applied = policy.applied_version;
  if (policy.source === "approved_baseline" || version === 0) {
    return "No saved policy yet. The worker uses the approved baseline until you save.";
  }
  if (policy.worker_confirmed === true && applied === version) {
    return `Worker confirmed saved version ${version}. The saved production settings are loaded.`;
  }
  return `Saved version ${version} is stored. It is not shown as loaded until the worker confirms version ${version}.`;
}

function settingList(record: Record<string, unknown> | null | undefined): string {
  if (!record) return "none";
  const parts = EXPERIMENTAL_KEYS.flatMap((key) => {
    const value = record[key];
    return value == null || value === "" ? [] : [`${key} ${String(value)}`];
  });
  return parts.length ? parts.join(", ") : "none";
}

export function policyStateLines(policy: {
  version?: number;
  applied_version?: number | null;
  worker_confirmed?: boolean;
  experimental?: Record<string, unknown> | null;
  experimental_promoted?: boolean;
  document?: Record<string, unknown> | null;
}): { experimental: string; savedProduction: string; workerLoaded: string } {
  const version = policy.version ?? 0;
  const experiment = policy.experimental;
  const experimental = experiment
    ? `Saved experimental settings on version ${version}: ${settingList(experiment)}. ${
        policy.experimental_promoted
          ? "Promotion is saved in that version."
          : "Promotion is off, so these values are not the live floor."
      }`
    : "No experimental settings are saved.";
  const savedProduction = version
    ? `Saved production policy version ${version}: ${settingList(policy.document)}. ${
        policy.worker_confirmed
          ? "The worker confirmed this version."
          : "Saved, not confirmed by the worker."
      }`
    : "No production policy is saved. The approved baseline is the fallback.";
  const workerLoaded = policy.worker_confirmed
    ? `Worker loaded version ${version}: ${settingList(policy.document)}.`
    : `Worker has not confirmed version ${version}. Last confirmed version: ${
        policy.applied_version ?? "none"
      }.`;
  return { experimental, savedProduction, workerLoaded };
}
