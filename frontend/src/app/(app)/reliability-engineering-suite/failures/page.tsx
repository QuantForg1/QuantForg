"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { ResFailuresWorkspace } from "@/components/ops/res-workspaces";

export default function ResFailuresPage() {
  return (
    <div>
      <PageHeader
        title="Failure Explorer"
        description="Classified gateway, broker, scheduler, strategy, infrastructure and data failures."
      />
      <PageMotion>
        <ResFailuresWorkspace />
      </PageMotion>
    </div>
  );
}
