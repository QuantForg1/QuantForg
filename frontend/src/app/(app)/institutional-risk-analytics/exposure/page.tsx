"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { IrapExposureWorkspace } from "@/components/ops/irap-workspaces";

export default function IrapExposurePage() {
  return (
    <div>
      <PageHeader
        title="Exposure Explorer"
        description="Session and symbol exposure, concentration and capital allocation."
      />
      <PageMotion>
        <IrapExposureWorkspace />
      </PageMotion>
    </div>
  );
}
