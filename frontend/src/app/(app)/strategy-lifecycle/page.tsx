"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Phase5LifecycleDesk } from "@/components/ops/phase5/lifecycle-desk";

export default function StrategyLifecyclePage() {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHeader
        eyebrow="Control Center"
        title="Strategy Lifecycle"
        description="Draft through archive — governance stages with explicit LIVE authorization gates."
      />
      <PageMotion className="min-h-0 flex-1 overflow-auto p-4">
        <Phase5LifecycleDesk />
      </PageMotion>
    </div>
  );
}
