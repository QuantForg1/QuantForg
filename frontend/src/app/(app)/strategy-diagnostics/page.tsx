"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { StrategyDiagnosticsWorkspace } from "@/components/ops/strategy-diagnostics-workspace";

export default function StrategyDiagnosticsPage() {
  return (
    <div>
      <PageHeader
        title="Strategy Diagnostics"
        description="Diagnose why the strategy produces NO_TRADE — quality, confluence components, MTF trend, and rejection reasons. Observation only: never mutates strategy, risk, safety, OMS, or MT5."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/auto-trading">Auto Trading</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/production-validation">Production Validation</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/performance-intelligence">Performance IQ</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <StrategyDiagnosticsWorkspace />
      </PageMotion>
    </div>
  );
}
