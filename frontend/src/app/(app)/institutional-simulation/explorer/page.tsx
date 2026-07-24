"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { IseExplorerWorkspace } from "@/components/ops/ise-workspaces";

export default function IseExplorerPage() {
  return (
    <div>
      <PageHeader
        title="Scenario Explorer"
        description="Browse stored digital-twin simulations and metrics."
      />
      <PageMotion>
        <IseExplorerWorkspace />
      </PageMotion>
    </div>
  );
}
