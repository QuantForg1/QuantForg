"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { CvfDriftWorkspace } from "@/components/ops/cvf-workspaces";

export default function CvfDriftPage() {
  return (
    <div>
      <PageHeader
        title="Drift Explorer"
        description="Win rate, PF, expectancy, drawdown, session and regime drift signals."
      />
      <PageMotion>
        <CvfDriftWorkspace />
      </PageMotion>
    </div>
  );
}
