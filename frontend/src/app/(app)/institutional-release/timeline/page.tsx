"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { IrdpTimelineWorkspace } from "@/components/ops/irdp-workspaces";

export default function IrdpTimelinePage() {
  return (
    <div>
      <PageHeader
        title="Release Timeline"
        description="Development → Testing → Validation → ISE → CVF → Human Approval → Staging → Production."
      />
      <PageMotion>
        <IrdpTimelineWorkspace />
      </PageMotion>
    </div>
  );
}
