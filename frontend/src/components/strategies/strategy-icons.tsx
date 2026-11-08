import type { LucideIcon } from "lucide-react";
import {
  Activity,
  BarChart2,
  Binary,
  GitBranch,
  LineChart,
  Sparkles,
  TrendingUp,
  Waves,
} from "lucide-react";

const ICON_BY_KEY: Record<string, LucideIcon> = {
  trend_following: TrendingUp,
  ma_cross: GitBranch,
  rsi: Activity,
  macd: LineChart,
  bollinger: Waves,
  breakout: BarChart2,
  momentum: TrendingUp,
  mean_reversion: Binary,
  custom_rules: Sparkles,
};

export function strategyIconForKey(key: string): LucideIcon {
  return ICON_BY_KEY[key] ?? Sparkles;
}
