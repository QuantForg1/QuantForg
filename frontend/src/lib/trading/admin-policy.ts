/** Build an owner policy save. A defer choice keeps the deployment flag. */

export type M1Choice = "defer" | "on" | "off";

export const POLICY_NUMERIC_KEYS = [
  "max_planned_risk_pct",
  "daily_loss_pct",
  "weekly_loss_pct",
  "max_drawdown_pct",
  "max_aggregate_open_risk_pct",
  "max_concurrent_positions",
  "min_lot",
  "max_lot",
  "max_spread",
  "min_reward_risk",
  "min_trade_quality",
  "stop_atr_multiplier",
] as const;

export const OWNER_COMMISSION = {
  symbol: "XAUUSD",
  account_scope: "ATTACHED_WELTRADE_REAL_HEDGE",
  amount_usd: "0.00",
  status: "VERIFIED_BY_OWNER_SUPPORT",
  source: "OWNER_CONFIRMED_WELTRADE_SUPPORT",
  model: "FIXED_ACCOUNT_CURRENCY_PER_ORDER",
  currency: "USD",
  configuration_version: "1",
  applies_to: "new_order_planned_risk",
  excludes: "spread,swap,slippage,broker_deal_history",
} as const;

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
    changes[key] =
      key === "min_trade_quality" || key === "max_concurrent_positions"
        ? Number(raw)
        : raw;
  }
  changes.m1_micro_enabled = m1DocumentValue(input.m1);
  changes.m1_live_submit = m1DocumentValue(input.m1Live);
  if (changes.max_concurrent_positions == null) {
    changes.max_concurrent_positions = 5;
  }
  changes.commission = { ...OWNER_COMMISSION };
  changes.gold_only = true;
  changes.protective_stop_required = true;
  changes.evaluate_full_utc_day = true;
  changes.ite_enabled = true;
  changes.unified_decision_enabled = true;
  return changes;
}

export const ACTIVE_RISK_CEILING = 20;
export const ACTIVE_AGGREGATE_CEILING = 30;
export const ACTIVE_DAILY_LOSS_CEILING = 48;
export const ACTIVE_SPREAD_CEILING = 1;
export const ACTIVE_POSITION_CEILING = 5;
export const ACTIVE_QUALITY_FLOOR = 70;
export const ACTIVE_REWARD_RISK_FLOOR = 0.5;
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
  max_planned_risk_pct: "20",
  max_aggregate_open_risk_pct: "30",
  daily_loss_pct: "48",
  max_lot: "0.01",
  max_spread: "1.00",
  min_reward_risk: "0.20",
  min_trade_quality: "70",
  stop_atr_multiplier: "1.00",
  max_concurrent_positions: "5",
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
  const daily = numeric(draft.daily_loss_pct || "");
  const spread = numeric(draft.max_spread || "");
  const positions = numeric(draft.max_concurrent_positions || "");
  const quality = numeric(draft.min_trade_quality || "");
  const reward = numeric(draft.min_reward_risk || "");
  if (risk != null && (risk <= 0 || risk > ACTIVE_RISK_CEILING)) {
    errors.push(`Planned risk ceiling is ${ACTIVE_RISK_CEILING}%.`);
  }
  if (aggregate != null && (aggregate <= 0 || aggregate > ACTIVE_AGGREGATE_CEILING)) {
    errors.push(`Aggregate open-risk ceiling is ${ACTIVE_AGGREGATE_CEILING}%.`);
  }
  if (risk != null && aggregate != null && aggregate < risk) {
    errors.push("Aggregate open risk cannot be below planned risk per trade.");
  }
  if (daily != null && (daily <= 0 || daily > ACTIVE_DAILY_LOSS_CEILING)) {
    errors.push(`Daily loss halt ceiling is ${ACTIVE_DAILY_LOSS_CEILING}%.`);
  }
  if (spread != null && (spread <= 0 || spread > ACTIVE_SPREAD_CEILING)) {
    errors.push(`Spread ceiling is ${ACTIVE_SPREAD_CEILING.toFixed(2)}.`);
  }
  if (
    positions != null &&
    (!Number.isInteger(positions) || positions < 1 || positions > ACTIVE_POSITION_CEILING)
  ) {
    errors.push(`Concurrent positions must be from 1 to ${ACTIVE_POSITION_CEILING}.`);
  }
  if (quality != null && (quality < ACTIVE_QUALITY_FLOOR || quality > 100)) {
    errors.push(`Minimum trade quality is ${ACTIVE_QUALITY_FLOOR} to 100, not 75.`);
  }
  if (reward != null && reward < ACTIVE_REWARD_RISK_FLOOR) {
    errors.push(
      "Active minimum reward/risk stays 0.50. Candidates 0.10, 0.15, and 0.20 are experimental and are not activated by this save.",
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

function rewardFloorNote(policy: {
  document?: Record<string, unknown> | null;
  enforced_min_reward_risk?: string;
}): string {
  const stored = policy.document?.min_reward_risk;
  const enforced = policy.enforced_min_reward_risk;
  if (stored == null || stored === "" || enforced == null || enforced === "") return "";
  if (String(stored) === enforced) return "";
  return ` Stored min_reward_risk ${String(stored)} is not the live floor. The worker enforces ${enforced}.`;
}

function commissionNote(policy: {
  commission?: Record<string, string> | null;
  document?: Record<string, unknown> | null;
}): string {
  const view = policy.commission;
  const usable = view?.commission_usable === "true";
  if (usable) {
    return ` Commission ${view?.commission_usd} USD, status ${view?.commission_status}, source ${view?.commission_source}, configuration ${view?.commission_configuration_version}.`;
  }
  const stored = policy.document?.commission;
  if (stored && typeof stored === "object") {
    return " Commission configuration is stored but not usable. Entries fail closed.";
  }
  return " Commission is not verified. Entries fail closed.";
}

export function policyStateLines(policy: {
  version?: number;
  applied_version?: number | null;
  worker_confirmed?: boolean;
  experimental?: Record<string, unknown> | null;
  experimental_promoted?: boolean;
  document?: Record<string, unknown> | null;
  enforced_min_reward_risk?: string;
  commission?: Record<string, string> | null;
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
  const floorNote = `${rewardFloorNote(policy)}${commissionNote(policy)}`;
  const savedProduction = version
    ? `Saved production policy version ${version}: ${settingList(policy.document)}. ${
        policy.worker_confirmed
          ? "The worker confirmed this version."
          : "Saved, not confirmed by the worker."
      }${floorNote}`
    : "No production policy is saved. The approved baseline is the fallback.";
  const workerLoaded = policy.worker_confirmed
    ? `Worker loaded version ${version}: ${settingList(policy.document)}.${floorNote}`
    : `Worker has not confirmed version ${version}. Last confirmed version: ${
        policy.applied_version ?? "none"
      }.${floorNote}`;
  return { experimental, savedProduction, workerLoaded };
}
