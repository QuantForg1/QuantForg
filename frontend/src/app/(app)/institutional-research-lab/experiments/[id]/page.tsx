"use client";

import { use } from "react";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { IrlExperimentDetailWorkspace } from "@/components/ops/irl-workspaces";

export default function IrlExperimentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  return (
    <div>
      <PageHeader
        title="Experiment details"
        description="Replay, statistics, significance, benchmark, and research notes — isolated from production."
      />
      <PageMotion>
        <IrlExperimentDetailWorkspace experimentId={id} />
      </PageMotion>
    </div>
  );
}
