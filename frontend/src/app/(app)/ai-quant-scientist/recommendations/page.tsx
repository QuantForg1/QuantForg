"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { AqsRecommendationsWorkspace } from "@/components/ops/aqs-workspaces";

export default function AqsRecommendationsPage() {
  return (
    <div>
      <PageHeader
        title="AQS Recommendation Center"
        description="Open · Accepted · Rejected · Archived. Accepted never changes production automatically."
      />
      <PageMotion>
        <AqsRecommendationsWorkspace />
      </PageMotion>
    </div>
  );
}
