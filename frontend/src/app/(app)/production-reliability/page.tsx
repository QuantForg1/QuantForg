"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { ProductionReliabilityWorkspace } from "@/components/ops/production-reliability-workspace";

export default function ProductionReliabilityPage() {
  return (
    <div>
      <PageHeader
        title="Production Reliability"
        description="Production hardening v6 — system health, live execution metrics, lifecycle timeline, explainability, incidents, learning, and secrets audit (names only). Observation + reliability; does not add experimental trading features."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/ops">Ops</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/monitoring">Monitoring</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/institutional-observability">Observability</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <ProductionReliabilityWorkspace />
      </PageMotion>
    </div>
  );
}
