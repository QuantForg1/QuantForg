"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { QptcmExplorerWorkspace } from "@/components/ops/qptcm-workspaces";

export default function QptcmExplorerPage() {
  return (
    <div>
      <PageHeader
        title="Campaign Explorer"
        description="QPTCM campaigns — lifecycle, market, window, objectives."
      />
      <PageMotion>
        <QptcmExplorerWorkspace />
      </PageMotion>
    </div>
  );
}
