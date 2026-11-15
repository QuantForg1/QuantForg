"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Phase6ReportsDesk } from "@/components/ops/phase6/reports-desk";

export default function InstitutionalReportsPage() {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHeader
        eyebrow="Intelligence"
        title="Institutional Reports"
        description="Composed performance and operations report catalogs with honest completeness."
      />
      <PageMotion className="min-h-0 flex-1 overflow-auto p-4">
        <Phase6ReportsDesk />
      </PageMotion>
    </div>
  );
}
