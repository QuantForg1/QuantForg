"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Phase8OptimizeDesk } from "@/components/ops/phase8/optimize-desk";

export default function StrategyOptimizationPage() {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHeader
        eyebrow="Research Factory"
        title="Strategy Optimization"
        description="Optimization lab with holdout honesty — optimized params never auto-deploy LIVE."
      />
      <PageMotion className="min-h-0 flex-1 overflow-auto p-4">
        <Phase8OptimizeDesk />
      </PageMotion>
    </div>
  );
}
