"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { QcsDashboardWorkspace } from "@/components/ops/qcs-workspaces";

export default function QuantForgCertificationPage() {
  return (
    <div>
      <PageHeader
        title="Certification Suite"
        description="QCS — institutional quality gate. Human approval required. Never modifies production."
      />
      <PageMotion>
        <QcsDashboardWorkspace />
      </PageMotion>
    </div>
  );
}
