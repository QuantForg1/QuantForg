"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { QemTimelineWorkspace } from "@/components/ops/qem-workspaces";

export default function QuantForgEventMeshTimelinePage() {
  return (
    <div>
      <PageHeader
        title="Event Timeline"
        description="QEM chronological history — immutable audit trail."
      />
      <PageMotion>
        <QemTimelineWorkspace />
      </PageMotion>
    </div>
  );
}
