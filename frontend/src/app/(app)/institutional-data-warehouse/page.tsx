"use client";

import { Database } from "lucide-react";
import { WorkspacePage } from "@/components/layout/workspace-page";
import { InstitutionalDataWarehouseWorkspace } from "@/components/ops/institutional-data-warehouse-workspace";

export default function InstitutionalDataWarehousePage() {
  return (
    <WorkspacePage
      title="Institutional Data Warehouse"
      description="Read-only analytics warehouse unifying market, trades, evidence, governance, and reports — never modifies production records or trading behaviour."
      icon={Database}
      actionLabel="Governance"
      actionHref="/audit-governance"
    >
      <InstitutionalDataWarehouseWorkspace />
    </WorkspacePage>
  );
}
