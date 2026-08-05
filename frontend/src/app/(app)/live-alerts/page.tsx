"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { LiveAlertsWorkspace } from "@/components/operator/live-alerts-workspace";

export default function Page() {
  return (
    <div>
      <PageHeader
        title="Live Alerts"
        description="Desktop / email / Telegram-ready alerts. Never executes."
      />
      <PageMotion>
        <LiveAlertsWorkspace />
      </PageMotion>
    </div>
  );
}
