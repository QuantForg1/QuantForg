"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { AqsFeedWorkspace } from "@/components/ops/aqs-workspaces";

export default function AqsFeedPage() {
  return (
    <div>
      <PageHeader title="AQS Research Feed" description="Continuous research recommendation feed." />
      <PageMotion>
        <AqsFeedWorkspace />
      </PageMotion>
    </div>
  );
}
