/**
 * Production feature flags.
 * Defaults come from NEXT_PUBLIC_FF_* env vars.
 * Operators can override at runtime via localStorage without redeploy
 * (see setFlagOverride / clearFlagOverrides).
 */

export type FeatureFlagKey =
  | "ai"
  | "mt5"
  | "paper"
  | "workspace"
  | "beta";

export type FeatureFlags = Record<FeatureFlagKey, boolean>;

const OVERRIDE_KEY = "qf.ff.overrides.v1";

const DEFAULTS: FeatureFlags = {
  ai: process.env.NEXT_PUBLIC_FF_AI !== "false",
  mt5: process.env.NEXT_PUBLIC_FF_MT5 !== "false",
  paper: process.env.NEXT_PUBLIC_FF_PAPER !== "false",
  workspace: process.env.NEXT_PUBLIC_FF_WORKSPACE !== "false",
  beta: process.env.NEXT_PUBLIC_FF_BETA === "true",
};

function readOverrides(): Partial<FeatureFlags> {
  if (typeof window === "undefined") return {};
  try {
    const raw = localStorage.getItem(OVERRIDE_KEY);
    return raw ? (JSON.parse(raw) as Partial<FeatureFlags>) : {};
  } catch {
    return {};
  }
}

export function getFeatureFlags(): FeatureFlags {
  const overrides = readOverrides();
  return { ...DEFAULTS, ...overrides };
}

export function isFeatureEnabled(key: FeatureFlagKey): boolean {
  return Boolean(getFeatureFlags()[key]);
}

export function setFlagOverride(key: FeatureFlagKey, value: boolean) {
  if (typeof window === "undefined") return;
  const next = { ...readOverrides(), [key]: value };
  localStorage.setItem(OVERRIDE_KEY, JSON.stringify(next));
}

export function clearFlagOverrides() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(OVERRIDE_KEY);
}

export function describeFlags(): Array<{ key: FeatureFlagKey; enabled: boolean; source: string }> {
  const overrides = readOverrides();
  return (Object.keys(DEFAULTS) as FeatureFlagKey[]).map((key) => ({
    key,
    enabled: getFeatureFlags()[key],
    source: key in overrides ? "override" : "env",
  }));
}
