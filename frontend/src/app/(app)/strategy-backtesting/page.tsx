"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Phase8BacktestDesk } from "@/components/ops/phase8/backtest-desk";

export default function StrategyBacktestingPage() {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHeader
        eyebrow="Research Factory"
        title="Strategy Backtesting"
        description="Backtest, walk-forward, and Monte Carlo compose — assumption disclosure; backtest ≠ LIVE."
      />
      <PageMotion className="min-h-0 flex-1 overflow-auto p-4">
        <Phase8BacktestDesk />
      </PageMotion>
    </div>
  );
}
