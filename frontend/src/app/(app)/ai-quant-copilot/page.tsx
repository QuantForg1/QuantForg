"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { AqcHomeWorkspace } from "@/components/ops/aqc-workspaces";

export default function AiQuantCopilotPage() {
  return (
    <div>
      <PageHeader
        title="AI Quant Copilot"
        description="Institutional AI operations assistant — investigations, evidence, and explanations. Never modifies production."
      />
      <PageMotion>
        <AqcHomeWorkspace />
      </PageMotion>
    </div>
  );
}
