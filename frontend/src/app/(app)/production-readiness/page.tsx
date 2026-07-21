"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { ProductionReadinessWorkspace } from "@/components/ops/production-readiness-workspace";

export default function ProductionReadinessPage() {
  return (
    <div>
      <PageHeader
        title="Production Readiness Program"
        description="Institutional reliability for production trading. Does not change execution architecture, never bypasses Risk or Safety, never places orders. Failures and recoveries are auditable; health policies are configurable."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/ops">Ops control</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/monitoring">Monitoring</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/mission-control">Mission Control</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/risk">Risk</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <ProductionReadinessWorkspace />
      </PageMotion>
    </div>
  );
}
