"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { ProductionReadinessCertificationWorkspace } from "@/components/ops/production-readiness-certification-workspace";

export default function ProductionReadinessCertificationPage() {
  return (
    <div>
      <PageHeader
        title="Production Readiness Certification"
        description="Final institutional certification framework for live capital readiness based on measurable evidence. Read-only — never places trades, never changes strategies or engines, never auto-configures. Human approval always required."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/institutional-validation-program">IVP</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/live-learning-program">LLP</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/production-readiness">Production Readiness</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <ProductionReadinessCertificationWorkspace />
      </PageMotion>
    </div>
  );
}
