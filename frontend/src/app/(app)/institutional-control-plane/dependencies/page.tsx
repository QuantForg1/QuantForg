"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { IcpDependenciesWorkspace } from "@/components/ops/icp-workspaces";

export default function IcpDependenciesPage() {
  return (
    <div>
      <PageHeader
        title="Dependency Explorer"
        description="Relationships between major QuantForg enterprise subsystems."
      />
      <PageMotion>
        <IcpDependenciesWorkspace />
      </PageMotion>
    </div>
  );
}
