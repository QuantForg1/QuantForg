"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { ResHealthWorkspace } from "@/components/ops/res-workspaces";

export default function ResHealthPage() {
  return (
    <div>
      <PageHeader
        title="Health Explorer"
        description="Per-service health, latency, restart and failure counts."
      />
      <PageMotion>
        <ResHealthWorkspace />
      </PageMotion>
    </div>
  );
}
