"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { IseWalkForwardWorkspace } from "@/components/ops/ise-workspaces";

export default function IseWalkForwardPage() {
  return (
    <div>
      <PageHeader
        title="Walk Forward"
        description="Train / validate / test splits with generalization score."
      />
      <PageMotion>
        <IseWalkForwardWorkspace />
      </PageMotion>
    </div>
  );
}
