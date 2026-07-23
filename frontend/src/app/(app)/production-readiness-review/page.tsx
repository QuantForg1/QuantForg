"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { ProductionReadinessReviewWorkspace } from "@/components/ops/production-readiness-review-workspace";

export default function ProductionReadinessReviewPage() {
  return (
    <div>
      <PageHeader
        title="Institutional Production Readiness Review"
        description="Read-only institutional audit — architecture, security, reliability, trading pipelines, data integrity, performance, and operations. Never modifies production trading behavior."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/production-readiness">Production Readiness</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/portfolio-analytics">Portfolio Analytics</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <ProductionReadinessReviewWorkspace />
      </PageMotion>
    </div>
  );
}
