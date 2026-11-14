"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { AocDashboardWorkspace } from "@/components/ops/aoc-workspaces";
import { Button } from "@/components/ui/button";

export default function QuantForgOperationsCenterPage() {
  return (
    <div>
      <PageHeader
        title="Operations Center"
        description="AOC — operational orchestration. Human approval required. Never remediates automatically."
        actions={
          <Button size="sm" variant="secondary" asChild>
            <Link href="/operations">Phase 5 Control Center</Link>
          </Button>
        }
      />
      <PageMotion>
        <AocDashboardWorkspace />
      </PageMotion>
    </div>
  );
}
