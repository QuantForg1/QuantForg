"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { AqsExplainWorkspace } from "@/components/ops/aqs-workspaces";

export default function AqsExplainPage() {
  return (
    <div>
      <PageHeader
        title="AQS Explainability Viewer"
        description="Evidence, statistics, confidence, counter-arguments, and risks for every recommendation."
      />
      <PageMotion>
        <AqsExplainWorkspace />
      </PageMotion>
    </div>
  );
}
