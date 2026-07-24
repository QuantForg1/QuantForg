"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { QdieRecommendationsWorkspace } from "@/components/ops/qdie-workspaces";

export default function QdieRecommendationsPage() {
  return (
    <div>
      <PageHeader
        title="Recommendation Explorer"
        description="QDIE explainable recommendations — evidence, alternatives, trade-offs."
      />
      <PageMotion>
        <QdieRecommendationsWorkspace />
      </PageMotion>
    </div>
  );
}
