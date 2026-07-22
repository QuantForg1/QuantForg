"use client";

import { FlaskConical } from "lucide-react";
import { WorkspacePage } from "@/components/layout/workspace-page";
import { ReplayEvidenceLabWorkspace } from "@/components/ops/replay-evidence-lab-workspace";

export default function ReplayEvidenceLabPage() {
  return (
    <WorkspacePage
      title="Replay & Evidence Lab"
      description="Historical XAUUSD replay, segregated evidence lanes, and confidence gates — advisory only; never modifies strategy, risk, safety, execution, or Performance IQ."
      icon={FlaskConical}
      actionLabel="Reports"
      actionHref="/reports"
    >
      <ReplayEvidenceLabWorkspace />
    </WorkspacePage>
  );
}
