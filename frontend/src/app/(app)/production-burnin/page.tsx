"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { ProductionBurnInWorkspace } from "@/components/ops/production-burnin-workspace";

export default function ProductionBurnInPage() {
  return (
    <div>
      <PageHeader
        title="Production Burn-in Monitor"
        description="Read-only stability desk until the first successful live fill. Never modifies Strategy, Risk, Safety, OMS, MT5, or session rules. Status is evidence-only — no manual override."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/production-acceptance">Acceptance</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/execution-timeline">Timeline</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/witness-health">Witness</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <ProductionBurnInWorkspace />
      </PageMotion>
    </div>
  );
}
