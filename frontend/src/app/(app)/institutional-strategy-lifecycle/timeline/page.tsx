"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { IslmTimelineWorkspace } from "@/components/ops/islm-workspaces";

export default function IslmTimelinePage() {
  return (
    <div>
      <PageHeader
        title="Lifecycle Timeline"
        description="Observational stage progression — transitions require explicit human approval."
      />
      <PageMotion>
        <IslmTimelineWorkspace />
      </PageMotion>
    </div>
  );
}
