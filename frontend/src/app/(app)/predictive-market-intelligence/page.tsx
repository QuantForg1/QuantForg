"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Phase6MarketDesk } from "@/components/ops/phase6/market-desk";

export default function PredictiveMarketIntelligencePage() {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHeader
        eyebrow="Intelligence"
        title="Predictive Market Intelligence"
        description="Regime, confidence and forecast limitations — never guaranteed outcomes."
      />
      <PageMotion className="min-h-0 flex-1 overflow-auto p-4">
        <Phase6MarketDesk />
      </PageMotion>
    </div>
  );
}
