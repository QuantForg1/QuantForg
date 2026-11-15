"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Phase6PortfolioDesk } from "@/components/ops/phase6/portfolio-desk";

export default function PortfolioOptimizationPage() {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHeader
        eyebrow="Intelligence"
        title="Portfolio Optimization"
        description="Allocation recommendations with assumptions — never auto-rebalance LIVE."
      />
      <PageMotion className="min-h-0 flex-1 overflow-auto p-4">
        <Phase6PortfolioDesk />
      </PageMotion>
    </div>
  );
}
