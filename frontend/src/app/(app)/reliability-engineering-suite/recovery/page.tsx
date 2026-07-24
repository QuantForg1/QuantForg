"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { ResRecoveryWorkspace } from "@/components/ops/res-workspaces";

export default function ResRecoveryPage() {
  return (
    <div>
      <PageHeader
        title="Recovery Explorer"
        description="MTTD, MTTR, recovery success rate, automatic vs manual recoveries."
      />
      <PageMotion>
        <ResRecoveryWorkspace />
      </PageMotion>
    </div>
  );
}
