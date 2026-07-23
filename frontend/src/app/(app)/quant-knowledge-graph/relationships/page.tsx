"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { QkgRelationshipsWorkspace } from "@/components/ops/qkg-workspaces";

export default function QkgRelationshipsPage() {
  return (
    <div>
      <PageHeader
        title="Relationship Viewer"
        description="Explore inbound and outbound knowledge edges for any node."
      />
      <PageMotion>
        <QkgRelationshipsWorkspace />
      </PageMotion>
    </div>
  );
}
