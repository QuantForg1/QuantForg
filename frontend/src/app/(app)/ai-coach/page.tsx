"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { AiCoachWorkspace } from "@/components/operator/ai-coach-workspace";

export default function Page() {
  return (
    <div>
      <PageHeader
        title="AI Coach"
        description="Recommendations only. Never executes trades."
      />
      <PageMotion>
        <AiCoachWorkspace />
      </PageMotion>
    </div>
  );
}
