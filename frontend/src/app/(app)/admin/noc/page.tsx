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
        title="NOC Command Center"
        description="Institutional production operations desk — real telemetry only. Observe-only: never mutates trading, risk, OMS, gateway, or MT5."
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
          </div>
        }
      />
      <PageMotion>
        <NocCommandCenter />
      </PageMotion>
    </div>
  );
}
