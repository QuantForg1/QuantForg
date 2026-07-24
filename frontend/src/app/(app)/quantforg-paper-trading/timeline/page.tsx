"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { QptcmTimelineWorkspace } from "@/components/ops/qptcm-workspaces";

export default function QptcmTimelinePage() {
  return (
    <div>
      <PageHeader
        title="Daily Timeline"
        description="QPTCM paper snapshots — fills, pnl, incidents."
      />
      <PageMotion>
        <QptcmTimelineWorkspace />
      </PageMotion>
    </div>
  );
}
