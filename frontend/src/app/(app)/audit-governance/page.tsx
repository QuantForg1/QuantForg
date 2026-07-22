"use client";

import { Scale } from "lucide-react";
import { WorkspacePage } from "@/components/layout/workspace-page";
import { AuditGovernanceWorkspace } from "@/components/ops/audit-governance-workspace";

export default function AuditGovernancePage() {
  return (
    <WorkspacePage
      title="Audit Trail & Governance"
      description="Immutable institutional audit trail, forensic timeline, configuration history, and operator accountability — governance only; never modifies trading behaviour."
      icon={Scale}
      actionLabel="Ops Center"
      actionHref="/trading-operations-center"
    >
      <AuditGovernanceWorkspace />
    </WorkspacePage>
  );
}
