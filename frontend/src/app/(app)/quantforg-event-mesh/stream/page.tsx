"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { QemStreamWorkspace } from "@/components/ops/qem-workspaces";

export default function QuantForgEventMeshStreamPage() {
  return (
    <div>
      <PageHeader
        title="Live Event Stream"
        description="QEM observational stream — chronological, immutable, read-only."
      />
      <PageMotion>
        <QemStreamWorkspace />
      </PageMotion>
    </div>
  );
}
