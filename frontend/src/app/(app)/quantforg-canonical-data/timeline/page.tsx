"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { QcdmTimelineWorkspace } from "@/components/ops/qcdm-workspaces";

export default function QuantForgCanonicalDataTimelinePage() {
  return (
    <div>
      <PageHeader
        title="Version Timeline"
        description="QCDM schema governance history — compatibility and deprecation."
      />
      <PageMotion>
        <QcdmTimelineWorkspace />
      </PageMotion>
    </div>
  );
}
