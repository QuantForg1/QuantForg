"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { QpmDiversificationWorkspace } from "@/components/ops/qpm-workspaces";

export default function QpmDiversificationPage() {
  return (
    <div>
      <PageHeader
        title="Diversification Matrix"
        description="Diversification score and pairwise correlation proxies — research only."
      />
      <PageMotion>
        <QpmDiversificationWorkspace />
      </PageMotion>
    </div>
  );
}
