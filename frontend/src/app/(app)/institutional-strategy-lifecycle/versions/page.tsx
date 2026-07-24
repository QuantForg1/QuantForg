"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { IslmVersionsWorkspace } from "@/components/ops/islm-workspaces";

export default function IslmVersionsPage() {
  return (
    <div>
      <PageHeader
        title="Version Explorer"
        description="Strategy version history and human-approved lifecycle transitions."
      />
      <PageMotion>
        <IslmVersionsWorkspace />
      </PageMotion>
    </div>
  );
}
