"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { IcpEvidenceWorkspace } from "@/components/ops/icp-workspaces";

export default function IcpEvidencePage() {
  return (
    <div>
      <PageHeader
        title="Evidence Center"
        description="Subsystem evidence packs and integrity checks — read-only."
      />
      <PageMotion>
        <IcpEvidenceWorkspace />
      </PageMotion>
    </div>
  );
}
