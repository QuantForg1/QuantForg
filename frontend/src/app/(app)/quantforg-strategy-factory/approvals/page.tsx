"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { QsfApprovalsWorkspace } from "@/components/ops/qsf-workspaces";

export default function QsfApprovalsPage() {
  return (
    <div>
      <PageHeader
        title="Approval Queue"
        description="QSF human-gated pipeline transitions — factory isolation only."
      />
      <PageMotion>
        <QsfApprovalsWorkspace />
      </PageMotion>
    </div>
  );
}
