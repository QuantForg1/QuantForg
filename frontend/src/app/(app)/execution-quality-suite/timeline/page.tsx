"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { EqsTimelineWorkspace } from "@/components/ops/eqs-workspaces";

export default function EqsTimelinePage() {
  return (
    <div>
      <PageHeader
        title="Execution Timeline"
        description="Signal → Risk → OMS → Gateway → Broker → Fill stage timestamps."
      />
      <PageMotion>
        <EqsTimelineWorkspace />
      </PageMotion>
    </div>
  );
}
