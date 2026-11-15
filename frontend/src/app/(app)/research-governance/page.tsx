"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Phase8GovernanceDesk } from "@/components/ops/phase8/governance-desk";

export default function ResearchGovernancePage() {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHeader
        eyebrow="Research Factory"
        title="Research Governance"
        description="Validation pipeline, approvals, and audit — Approved ≠ LIVE; paper ≠ LIVE."
      />
      <PageMotion className="min-h-0 flex-1 overflow-auto p-4">
        <Phase8GovernanceDesk />
      </PageMotion>
    </div>
  );
}
