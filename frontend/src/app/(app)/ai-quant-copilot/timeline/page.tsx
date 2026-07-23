"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { AqcTimelineWorkspace } from "@/components/ops/aqc-workspaces";

export default function AqcTimelinePage() {
  return (
    <div>
      <PageHeader
        title="Timeline Explorer"
        description="Chronological operational events across ICC, audit, and opportunity."
      />
      <PageMotion>
        <AqcTimelineWorkspace />
      </PageMotion>
    </div>
  );
}
