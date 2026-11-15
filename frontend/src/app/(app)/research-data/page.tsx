"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Phase8DataDesk } from "@/components/ops/phase8/data-desk";

export default function ResearchDataPage() {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHeader
        eyebrow="Research Factory"
        title="Research Data"
        description="Historical data quality and availability — never fabricates OHLCV."
      />
      <PageMotion className="min-h-0 flex-1 overflow-auto p-4">
        <Phase8DataDesk />
      </PageMotion>
    </div>
  );
}
