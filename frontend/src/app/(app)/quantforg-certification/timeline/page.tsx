"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { QcsTimelineWorkspace } from "@/components/ops/qcs-workspaces";

export default function QcsTimelinePage() {
  return (
    <div>
      <PageHeader
        title="Certification Timeline"
        description="Observational assessment history — never auto-certifies."
      />
      <PageMotion>
        <QcsTimelineWorkspace />
      </PageMotion>
    </div>
  );
}
