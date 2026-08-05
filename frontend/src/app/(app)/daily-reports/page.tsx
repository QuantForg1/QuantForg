"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { DailyReportsWorkspace } from "@/components/operator/daily-reports-workspace";

export default function Page() {
  return (
    <div>
      <PageHeader
        title="Daily Reports"
        description="Daily, weekly, and monthly institutional reports from LIVE fills."
      />
      <PageMotion>
        <DailyReportsWorkspace />
      </PageMotion>
    </div>
  );
}
