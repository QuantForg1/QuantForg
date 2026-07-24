"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { QsfPipelineWorkspace } from "@/components/ops/qsf-workspaces";

export default function QsfPipelinePage() {
  return (
    <div>
      <PageHeader
        title="Pipeline Board"
        description="QSF stage board — Idea through Paper Trading Ready."
      />
      <PageMotion>
        <QsfPipelineWorkspace />
      </PageMotion>
    </div>
  );
}
