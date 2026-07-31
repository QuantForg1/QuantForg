"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { NocCommandCenter } from "@/components/ops/noc/noc-command-center";

export default function AdminNocPage() {
  return (
    <div>
      <PageHeader
        title="Trading Command Center"
        description="QuantForg institutional NOC — Bloomberg-style live telemetry. RC4 charcoal · observe-only · never mutates trading, AI, risk, OMS, gateway, or MT5."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/production-validation">Validation</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/monitoring">Monitoring</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/ops">Ops Control</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/admin/customer-ops">Customer Ops</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <NocCommandCenter />
      </PageMotion>
    </div>
  );
}
