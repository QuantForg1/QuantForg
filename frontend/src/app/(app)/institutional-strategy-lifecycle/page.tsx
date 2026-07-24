"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { IslmRegistryWorkspace } from "@/components/ops/islm-workspaces";

export default function InstitutionalStrategyLifecyclePage() {
  return (
    <div>
      <PageHeader
        title="Strategy Lifecycle"
        description="ISLM — track strategies from Draft to Retired. Human approval required. Never modifies production."
      />
      <PageMotion>
        <IslmRegistryWorkspace />
      </PageMotion>
    </div>
  );
}
