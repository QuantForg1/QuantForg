"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { ExecutiveDashboardWorkspace } from "@/components/operator/executive-dashboard-workspace";

export default function Page() {
  return (
    <div>
      <PageHeader
        title="Executive Dashboard"
        description="CEO view — capital, PnL, growth, allocation, system status."
      />
      <PageMotion>
        <ExecutiveDashboardWorkspace />
      </PageMotion>
    </div>
  );
}
