"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { ProductionAcceptanceWorkspace } from "@/components/ops/production-acceptance-workspace";

export default function ProductionAcceptancePage() {
  return (
    <div>
      <PageHeader
        title="Production Acceptance"
        description="Read-only certification desk. Observes live production evidence and records the first legitimate fill — never mutates the trading engine."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/auto-trading">Trading Ops</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/production-validation">Validation</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/production-acceptance-countdown">Countdown</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/monitoring">Monitoring</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <ProductionAcceptanceWorkspace />
      </PageMotion>
    </div>
  );
}
