"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { CustomerOperationsPlatform } from "@/components/ops/customer-operations-platform";

export default function CustomerOpsPage() {
  return (
    <div>
      <PageHeader
        title="Customer Operations Platform"
        description="Institutional COP — fleet, licenses, brokers, support, audit, notifications. Additive ops only — never modifies trading, AI, OMS, MT5, or Risk."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/admin/noc">NOC</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/audit-governance">Governance</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <CustomerOperationsPlatform />
      </PageMotion>
    </div>
  );
}
