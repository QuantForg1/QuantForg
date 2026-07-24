"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { AocRecommendationsWorkspace } from "@/components/ops/aoc-workspaces";

export default function AocRecommendationsPage() {
  return (
    <div>
      <PageHeader
        title="Recommendation Center"
        description="Operator recommendations with evidence — never auto-applied."
      />
      <PageMotion>
        <AocRecommendationsWorkspace />
      </PageMotion>
    </div>
  );
}
