"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { IepRegistryWorkspace } from "@/components/ops/iep-workspaces";

export default function InstitutionalExperimentationPage() {
  return (
    <div>
      <PageHeader
        title="Experimentation Platform"
        description="IEP — governed research experiments. Never modifies production or promotes automatically."
      />
      <PageMotion>
        <IepRegistryWorkspace />
      </PageMotion>
    </div>
  );
}
