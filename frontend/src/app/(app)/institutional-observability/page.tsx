"use client";

import { Radar } from "lucide-react";
import { WorkspacePage } from "@/components/layout/workspace-page";
import { InstitutionalObservabilityWorkspace } from "@/components/ops/institutional-observability-workspace";

export default function InstitutionalObservabilityPage() {
  return (
    <WorkspacePage
      title="Institutional Observability"
      description="System health, latency, resources, uptime, dependency map, and alerts — monitoring only; never modifies trading behaviour."
      icon={Radar}
      actionLabel="Data Warehouse"
      actionHref="/institutional-data-warehouse"
    >
      <InstitutionalObservabilityWorkspace />
    </WorkspacePage>
  );
}
