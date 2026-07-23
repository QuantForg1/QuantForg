"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { ExecutionTimelineWorkspace } from "@/components/ops/execution-timeline-workspace";

export default function ExecutionTimelinePage() {
  return (
    <div>
      <PageHeader
        title="Execution Timeline"
        description="Read-only chronological stages from live cycles — snapshot through deal. Never modifies Strategy, Risk, Safety, OMS, or MT5."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/auto-trading">Trading Ops</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/session-readiness">Session Readiness</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/first-execution-evidence">First Evidence</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <ExecutionTimelineWorkspace />
      </PageMotion>
    </div>
  );
}
