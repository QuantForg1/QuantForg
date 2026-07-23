"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { IrlExperimentsWorkspace } from "@/components/ops/irl-workspaces";

export default function IrlExperimentsPage() {
  return (
    <div>
      <PageHeader
        title="IRL Experiments"
        description="Research experiments with candidate-only parameters. Production engines remain immutable."
      />
      <PageMotion>
        <IrlExperimentsWorkspace />
      </PageMotion>
    </div>
  );
}
