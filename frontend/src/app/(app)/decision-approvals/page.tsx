"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Phase7ApprovalsDesk } from "@/components/ops/phase7/approvals-desk";

export default function DecisionApprovalsPage() {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHeader
        eyebrow="Autonomy"
        title="Decision Approvals"
        description="Human approval workspace. Bound parameters; Approved ≠ LIVE."
      />
      <PageMotion className="min-h-0 flex-1 overflow-auto p-4">
        <Phase7ApprovalsDesk />
      </PageMotion>
    </div>
  );
}
