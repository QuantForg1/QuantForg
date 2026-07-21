"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { ProductionOpsDashboard } from "@/components/ops/production-ops-dashboard";

export default function MonitoringPage() {
  return (
    <div>
      <PageHeader
        title="Monitoring"
        description="Production operations dashboard — live execution timings, platform health, gateway, and reliability. Trading stays on Terminal; broker attach stays on Broker."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/broker">Broker</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/gateway">Gateway</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/execution/diagnostics">Execution Audit</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <ProductionOpsDashboard />
      </PageMotion>
    </div>
  );
}
