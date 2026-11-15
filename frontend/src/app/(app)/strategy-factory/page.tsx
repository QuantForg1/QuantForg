"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Phase8FactoryDesk } from "@/components/ops/phase8/factory-desk";

export default function StrategyFactoryPage() {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHeader
        eyebrow="Research Factory"
        title="Strategy Factory"
        description="Spec templates and advisory AI hypotheses — compose QSF; never execute arbitrary code or LIVE deploy."
      />
      <PageMotion className="min-h-0 flex-1 overflow-auto p-4">
        <Phase8FactoryDesk />
      </PageMotion>
    </div>
  );
}
