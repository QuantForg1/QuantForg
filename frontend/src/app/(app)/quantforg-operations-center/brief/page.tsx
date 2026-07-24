"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { AocBriefWorkspace } from "@/components/ops/aoc-workspaces";

export default function AocBriefPage() {
  return (
    <div>
      <PageHeader
        title="Executive Brief"
        description="Readiness scores and watch summaries across the platform."
      />
      <PageMotion>
        <AocBriefWorkspace />
      </PageMotion>
    </div>
  );
}
