/** Operator strategy module toggles — preferences only; never bypass risk/execution. */

export type StrategyModuleId =
  | "smart_money_concepts"
  | "liquidity_sweep"
  | "bos"
  | "choch"
  | "order_block"
  | "fair_value_gap";

export type StrategyModule = {
  id: StrategyModuleId;
  label: string;
  hint: string;
};

export const AUTO_STRATEGY_MODULES: StrategyModule[] = [
  {
    id: "smart_money_concepts",
    label: "Smart Money Concepts",
    hint: "Composite SMC confluence",
  },
  {
    id: "liquidity_sweep",
    label: "Liquidity Sweep",
    hint: "Sweep of equal highs/lows",
  },
  {
    id: "bos",
    label: "BOS",
    hint: "Break of structure",
  },
  {
    id: "choch",
    label: "CHOCH",
    hint: "Change of character",
  },
  {
    id: "order_block",
    label: "Order Block",
    hint: "Institutional order block",
  },
  {
    id: "fair_value_gap",
    label: "Fair Value Gap",
    hint: "Imbalance / FVG fill",
  },
];

const KEY = "qf.auto.strategies.v1";

export type StrategyToggleState = Record<StrategyModuleId, boolean>;

export function defaultStrategyToggles(): StrategyToggleState {
  return {
    smart_money_concepts: true,
    liquidity_sweep: true,
    bos: true,
    choch: true,
    order_block: true,
    fair_value_gap: true,
  };
}

export function loadStrategyToggles(): StrategyToggleState {
  const base = defaultStrategyToggles();
  if (typeof window === "undefined") return base;
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return base;
    const parsed = JSON.parse(raw) as Partial<StrategyToggleState>;
    return { ...base, ...parsed };
  } catch {
    return base;
  }
}

export function saveStrategyToggles(state: StrategyToggleState): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(KEY, JSON.stringify(state));
  } catch {
    /* ignore */
  }
}
