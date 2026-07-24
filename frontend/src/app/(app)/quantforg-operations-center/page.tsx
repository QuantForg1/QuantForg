"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { AocDashboardWorkspace } from "@/components/ops/aoc-workspaces";

export default function QuantForgOperationsCenterPage() {
  return (
    <div>
      <PageHeader
        title="Operations Center"
        description="AOC — operational orchestration. Human approval required. Never remediates automatically."
      />
      <PageMotion>
        <AocDashboardWorkspace />
      </PageMotion>
    </div>
  );
}
