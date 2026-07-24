"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { IrdpRollbacksWorkspace } from "@/components/ops/irdp-workspaces";

export default function IrdpRollbacksPage() {
  return (
    <div>
      <PageHeader
        title="Rollback Explorer"
        description="Controlled rollback plans and history — never executed automatically."
      />
      <PageMotion>
        <IrdpRollbacksWorkspace />
      </PageMotion>
    </div>
  );
}
