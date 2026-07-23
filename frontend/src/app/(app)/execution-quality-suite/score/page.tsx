"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { EqsScoreWorkspace } from "@/components/ops/eqs-workspaces";

export default function EqsScorePage() {
  return (
    <div>
      <PageHeader
        title="Execution Score"
        description="Composite 0–100 score across latency, slippage, fills, consistency, reliability."
      />
      <PageMotion>
        <EqsScoreWorkspace />
      </PageMotion>
    </div>
  );
}
