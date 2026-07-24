"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { QcdmSchemaExplorerWorkspace } from "@/components/ops/qcdm-workspaces";

export default function QuantForgCanonicalDataPage() {
  return (
    <div>
      <PageHeader
        title="Canonical Data Model"
        description="QCDM — enterprise data contract. Schema metadata only. Never modifies production."
      />
      <PageMotion>
        <QcdmSchemaExplorerWorkspace />
      </PageMotion>
    </div>
  );
}
