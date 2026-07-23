"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { OperationsRunbookWorkspace } from "@/components/ops/operations-runbook-workspace";

export default function OperationsRunbookPage() {
  return (
    <div>
      <PageHeader
        title="Operations Runbook"
        description="Read-only operator guidance by execution state — condition, blocker, evidence, and recommended action. Never modifies Strategy, Risk, Safety, OMS, or MT5."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/auto-trading">Trading Ops</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/automatic-production-acceptance">Auto Acceptance</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/execution-timeline">Timeline</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <OperationsRunbookWorkspace />
      </PageMotion>
    </div>
  );
}
