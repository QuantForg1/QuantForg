"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Phase6StrategyDesk } from "@/components/ops/phase6/strategy-desk";

export default function StrategyAnalyticsPage() {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHeader
        eyebrow="Intelligence"
        title="Strategy Analytics"
        description="Historical strategy metrics with explicit backtest / paper / live labeling."
      />
      <PageMotion className="min-h-0 flex-1 overflow-auto p-4">
        <Phase6StrategyDesk />
      </PageMotion>
    </div>
  );
}
