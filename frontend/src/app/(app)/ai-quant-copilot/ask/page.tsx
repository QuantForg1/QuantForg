"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { AqcAskWorkspace } from "@/components/ops/aqc-workspaces";

export default function AqcAskPage() {
  return (
    <div>
      <PageHeader
        title="Ask Copilot"
        description="Operational Q&A with mandatory evidence. Humans decide."
      />
      <PageMotion>
        <AqcAskWorkspace />
      </PageMotion>
    </div>
  );
}
