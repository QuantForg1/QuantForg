"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { ProductionValidationWorkspace } from "@/components/ops/production-validation-workspace";

export default function ProductionValidationPage() {
  return (
    <div>
      <PageHeader
        title="Production Validation"
        description="Real-time institutional validation desk — system, market, strategy, decision, risk, safety, execution, and journal. Observation only: never mutates trading rules or injects trades."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/auto-trading">Auto Trading</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/monitoring">Monitoring</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/production-readiness-certification">PRC</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <ProductionValidationWorkspace />
      </PageMotion>
    </div>
  );
}
