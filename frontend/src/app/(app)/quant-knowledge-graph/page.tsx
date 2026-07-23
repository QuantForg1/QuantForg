"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { QkgExplorerWorkspace } from "@/components/ops/qkg-workspaces";

export default function QuantKnowledgeGraphPage() {
  return (
    <div>
      <PageHeader
        title="Quant Knowledge Graph"
        description="Institutional knowledge layer — nodes, relationships, evidence. Never modifies production."
      />
      <PageMotion>
        <QkgExplorerWorkspace />
      </PageMotion>
    </div>
  );
}
