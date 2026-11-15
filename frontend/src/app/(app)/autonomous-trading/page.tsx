"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Phase7TradingDesk } from "@/components/ops/phase7/trading-desk";

export default function AutonomousTradingPage() {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHeader
        eyebrow="Autonomy"
        title="Autonomous Trading"
        description="Unified AI decision workspace — advisory candidates, NO TRADE honesty, never LIVE dispatch from Phase 7."
      />
      <PageMotion className="min-h-0 flex-1 overflow-auto p-4">
        <Phase7TradingDesk />
      </PageMotion>
    </div>
  );
}
