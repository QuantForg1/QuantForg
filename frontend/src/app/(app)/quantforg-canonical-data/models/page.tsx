"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { QcdmModelBrowserWorkspace } from "@/components/ops/qcdm-workspaces";

export default function QuantForgCanonicalDataModelsPage() {
  return (
    <div>
      <PageHeader
        title="Model Browser"
        description="QCDM canonical models — fields, validation rules, relationships."
      />
      <PageMotion>
        <QcdmModelBrowserWorkspace />
      </PageMotion>
    </div>
  );
}
