"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { CvfReportsWorkspace } from "@/components/ops/cvf-workspaces";

export default function CvfReportsPage() {
  return (
    <div>
      <PageHeader
        title="Validation Reports"
        description="Daily, weekly, monthly and quarterly executive validation reports."
      />
      <PageMotion>
        <CvfReportsWorkspace />
      </PageMotion>
    </div>
  );
}
