"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { IntegrationSprintV1Workspace } from "@/components/ops/integration-sprint-v1-workspace";

export default function IntegrationSprintV1Page() {
  return (
    <div>
      <PageHeader
        title="Integration Sprint V1"
        description="Production-grade read-only feeds and unified data bus for MT5 trades, positions, market data, account, execution journal, analytics, warehouse, economic calendar, and durable research storage. Never modifies Auto Trading, Execution, Decision, Risk, or Safety. Existing advisory APIs preserved."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/institutional-validation-program">IVP</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/live-learning-program">LLP</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/production-readiness-certification">PRC</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <IntegrationSprintV1Workspace />
      </PageMotion>
    </div>
  );
}
