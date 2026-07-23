"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { ProductionReplayWorkspace } from "@/components/ops/production-replay-workspace";

export default function ProductionReplayPage() {
  return (
    <div>
      <PageHeader
        title="Production Replay & Validation"
        description="Bounded, simulation-only walk-forward replay of the unchanged institutional analysis and decision pipeline across London / New York / overlap sessions. Never places an order, never mutates Risk, Safety, OMS, or the strategy engines."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/production-acceptance">Production Acceptance</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/production-readiness">Readiness</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <ProductionReplayWorkspace />
      </PageMotion>
    </div>
  );
}
