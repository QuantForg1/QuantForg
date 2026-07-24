"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { IrapStressWorkspace } from "@/components/ops/irap-workspaces";

export default function IrapStressPage() {
  return (
    <div>
      <PageHeader
        title="Stress Risk Explorer"
        description="ISE stress scenarios, VaR/CVaR and tail risk severity."
      />
      <PageMotion>
        <IrapStressWorkspace />
      </PageMotion>
    </div>
  );
}
