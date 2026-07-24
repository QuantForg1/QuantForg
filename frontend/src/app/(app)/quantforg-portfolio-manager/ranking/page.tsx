"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { QpmRankingWorkspace } from "@/components/ops/qpm-workspaces";

export default function QpmRankingPage() {
  return (
    <div>
      <PageHeader
        title="Strategy Ranking"
        description="Composite ranking across validation, risk, execution and certification."
      />
      <PageMotion>
        <QpmRankingWorkspace />
      </PageMotion>
    </div>
  );
}
