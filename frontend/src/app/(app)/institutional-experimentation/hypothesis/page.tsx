"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { IepHypothesisWorkspace } from "@/components/ops/iep-workspaces";

export default function IepHypothesisPage() {
  return (
    <div>
      <PageHeader
        title="Hypothesis Builder"
        description="Research scaffolds only — never modifies strategies or production."
      />
      <PageMotion>
        <IepHypothesisWorkspace />
      </PageMotion>
    </div>
  );
}
