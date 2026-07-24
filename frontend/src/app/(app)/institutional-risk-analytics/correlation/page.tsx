"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { IrapCorrelationWorkspace } from "@/components/ops/irap-workspaces";

export default function IrapCorrelationPage() {
  return (
    <div>
      <PageHeader
        title="Correlation Matrix"
        description="Observational session correlation matrix from portfolio behavior."
      />
      <PageMotion>
        <IrapCorrelationWorkspace />
      </PageMotion>
    </div>
  );
}
