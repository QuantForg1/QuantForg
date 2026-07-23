"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { IrlJobsWorkspace } from "@/components/ops/irl-workspaces";

export default function IrlJobsPage() {
  return (
    <div>
      <PageHeader
        title="IRL Replay Jobs"
        description="Historical / research replay jobs only — never live execution."
      />
      <PageMotion>
        <IrlJobsWorkspace />
      </PageMotion>
    </div>
  );
}
