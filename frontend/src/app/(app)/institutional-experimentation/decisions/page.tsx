"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { IepDecisionsWorkspace } from "@/components/ops/iep-workspaces";

export default function IepDecisionsPage() {
  return (
    <div>
      <PageHeader
        title="Decision Dashboard"
        description="Human decision queue — never auto-approves or auto-promotes."
      />
      <PageMotion>
        <IepDecisionsWorkspace />
      </PageMotion>
    </div>
  );
}
