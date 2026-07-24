"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { QcdmRelationshipWorkspace } from "@/components/ops/qcdm-workspaces";

export default function QuantForgCanonicalDataRelationshipsPage() {
  return (
    <div>
      <PageHeader
        title="Relationship Explorer"
        description="QCDM cross-model relationships — loosely documented, never mutating."
      />
      <PageMotion>
        <QcdmRelationshipWorkspace />
      </PageMotion>
    </div>
  );
}
