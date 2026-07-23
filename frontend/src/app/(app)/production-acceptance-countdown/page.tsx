"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { ProductionAcceptanceCountdownWorkspace } from "@/components/ops/production-acceptance-countdown-workspace";

export default function ProductionAcceptanceCountdownPage() {
  return (
    <div>
      <PageHeader
        title="Production Acceptance Countdown"
        description="Read-only operational countdown to first eligible live fill. Never modifies Strategy, Risk, Safety, OMS, MT5, sessions, or the trading engine."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/production-acceptance">Acceptance</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/auto-trading">Trading Ops</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/production-validation">Validation</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <ProductionAcceptanceCountdownWorkspace />
      </PageMotion>
    </div>
  );
}
