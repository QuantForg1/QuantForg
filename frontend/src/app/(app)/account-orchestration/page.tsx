"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Phase5AccountsDesk } from "@/components/ops/phase5/accounts-desk";

export default function AccountOrchestrationPage() {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHeader
        eyebrow="Control Center"
        title="Account Orchestration"
        description="Multi-account routing, worker health, and capacity-aware observe-only controls."
      />
      <PageMotion className="min-h-0 flex-1 overflow-auto p-4">
        <Phase5AccountsDesk />
      </PageMotion>
    </div>
  );
}
