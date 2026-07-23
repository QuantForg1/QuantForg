"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { FirstExecutionEvidenceWorkspace } from "@/components/ops/first-execution-evidence-workspace";

export default function FirstExecutionEvidencePage() {
  return (
    <div>
      <PageHeader
        title="First Execution Evidence"
        description="Immutable write-once record of the first successful live fill. Observation only — never modifies Strategy, Risk, Safety, OMS, or MT5 execution."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/production-acceptance">Acceptance</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/production-acceptance-countdown">Countdown</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/auto-trading">Trading Ops</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <FirstExecutionEvidenceWorkspace />
      </PageMotion>
    </div>
  );
}
