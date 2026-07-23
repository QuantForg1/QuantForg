"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { AqsCompareWorkspace } from "@/components/ops/aqs-workspaces";

export default function AqsComparePage() {
  return (
    <div>
      <PageHeader
        title="AQS Strategy Comparator"
        description="Production vs candidates vs replay experiments — research only."
      />
      <PageMotion>
        <AqsCompareWorkspace />
      </PageMotion>
    </div>
  );
}
