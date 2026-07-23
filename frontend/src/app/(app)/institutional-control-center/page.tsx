"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { InstitutionalControlCenterWorkspace } from "@/components/ops/institutional-control-center-workspace";

export default function InstitutionalControlCenterPage() {
  return (
    <div>
      <PageHeader
        title="Institutional Control Center"
        description="Single read-only operational cockpit — system status, live trading, portfolio, research, warehouse, alerts, and architecture. Never influences trading."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/mission-control">Mission Control</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/production-readiness-review">PRR</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <InstitutionalControlCenterWorkspace />
      </PageMotion>
    </div>
  );
}
