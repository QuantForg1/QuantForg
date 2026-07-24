"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { QdieTradeoffWorkspace } from "@/components/ops/qdie-workspaces";

export default function QdieTradeoffsPage() {
  return (
    <div>
      <PageHeader
        title="Trade-off Viewer"
        description="QDIE alternatives and trade-offs for each advisory decision."
      />
      <PageMotion>
        <QdieTradeoffWorkspace />
      </PageMotion>
    </div>
  );
}
