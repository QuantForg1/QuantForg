"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { PerformanceAnalyticsWorkspace } from "@/components/operator/performance-analytics-workspace";

export default function Page() {
  return (
    <div>
      <PageHeader
        title="Performance Analytics"
        description="Per symbol, session, strategy, day, week, month — LIVE only."
      />
      <PageMotion>
        <PerformanceAnalyticsWorkspace />
      </PageMotion>
    </div>
  );
}
