"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { AqcRecommendationsWorkspace } from "@/components/ops/aqc-workspaces";

export default function AqcRecommendationsPage() {
  return (
    <div>
      <PageHeader
        title="Recommendations Explorer"
        description="Search AQS recommendations by confidence, status, and research area."
      />
      <PageMotion>
        <AqcRecommendationsWorkspace />
      </PageMotion>
    </div>
  );
}
