"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Phase5IncidentDesk } from "@/components/ops/phase5/incident-desk";

export default function IncidentCenterPage() {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHeader
        eyebrow="Control Center"
        title="Incident Center"
        description="Unified incidents across reliability, workers, and execution — safe recovery only."
      />
      <PageMotion className="min-h-0 flex-1 overflow-auto p-4">
        <Phase5IncidentDesk />
      </PageMotion>
    </div>
  );
}
