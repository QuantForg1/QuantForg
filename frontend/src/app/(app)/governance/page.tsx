"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Phase5GovernanceDesk } from "@/components/ops/phase5/governance-desk";

export default function GovernancePage() {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHeader
        eyebrow="Control Center"
        title="Governance"
        description="Approval queue, operational audit trail, and institutional accountability."
      />
      <PageMotion className="min-h-0 flex-1 overflow-auto p-4">
        <Phase5GovernanceDesk />
      </PageMotion>
    </div>
  );
}
