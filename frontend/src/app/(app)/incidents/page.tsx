"use client";

import { AlertTriangle } from "lucide-react";
import { WorkspacePage } from "@/components/layout/workspace-page";

export default function IncidentsPage() {
  return (
    <WorkspacePage
      title="Incidents"
      description="Active incidents and reliability events."
      icon={AlertTriangle}
      emptyTitle="No active incidents"
      emptyDescription="Incident tracking attaches when observability is connected."
      actionLabel="Open Monitoring"
      actionHref="/monitoring"
    />
  );
}
