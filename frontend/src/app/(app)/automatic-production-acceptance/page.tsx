"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { AutomaticProductionAcceptanceWorkspace } from "@/components/ops/automatic-production-acceptance-workspace";

export default function AutomaticProductionAcceptancePage() {
  return (
    <div>
      <PageHeader
        title="Automatic Production Acceptance"
        description="Evidence-only engine: freezes an immutable acceptance report when Signal, Decision, Risk, Safety, OMS, Broker, MT5, Deal, and Journal are all observed. No manual override. Never modifies trading logic."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/production-acceptance">Acceptance Desk</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/first-execution-evidence">First Evidence</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/production-burnin">Burn-in</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <AutomaticProductionAcceptanceWorkspace />
      </PageMotion>
    </div>
  );
}
