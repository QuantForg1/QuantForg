"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { ProductionReliabilityProgram } from "@/components/ops/production-reliability-program";

export default function ReliabilityAdminPage() {
  return (
    <div>
      <PageHeader
        title="Production Reliability"
        description="Observability, SLA/SLO, incidents, backup/DR, health, ops reports, security ops, and performance — additive operational excellence. Never modifies trading, AI, OMS, MT5, auth, or pricing."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/admin/noc">NOC</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/admin/enterprise">Enterprise</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/admin/customer-ops">Customer Ops</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <ProductionReliabilityProgram />
      </PageMotion>
    </div>
  );
}
