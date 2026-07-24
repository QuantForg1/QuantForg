"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { QemExplorerWorkspace } from "@/components/ops/qem-workspaces";

export default function QuantForgEventMeshPage() {
  return (
    <div>
      <PageHeader
        title="Event Mesh"
        description="QEM — read-only institutional event backbone. Immutable distribution. Never modifies production."
      />
      <PageMotion>
        <QemExplorerWorkspace />
      </PageMotion>
    </div>
  );
}
