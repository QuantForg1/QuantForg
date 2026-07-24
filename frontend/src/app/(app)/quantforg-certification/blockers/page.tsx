"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { QcsBlockersWorkspace } from "@/components/ops/qcs-workspaces";

export default function QcsBlockersPage() {
  return (
    <div>
      <PageHeader
        title="Blocker Center"
        description="Read-only blockers with supporting evidence — blocks auto-release."
      />
      <PageMotion>
        <QcsBlockersWorkspace />
      </PageMotion>
    </div>
  );
}
