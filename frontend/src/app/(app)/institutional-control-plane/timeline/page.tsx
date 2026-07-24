"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { IcpTimelineWorkspace } from "@/components/ops/icp-workspaces";

export default function IcpTimelinePage() {
  return (
    <div>
      <PageHeader
        title="Global Timeline"
        description="Releases, experiments, lifecycle, validation, risk, reliability and execution events."
      />
      <PageMotion>
        <IcpTimelineWorkspace />
      </PageMotion>
    </div>
  );
}
