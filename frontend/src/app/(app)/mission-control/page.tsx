"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { MissionControlWorkspace } from "@/components/ops/mission-control-workspace";

export default function MissionControlPage() {
  return (
    <div>
      <PageHeader
        title="Mission Control"
        description="Institutional executive dashboard for platform supervision. Not Monitoring — live production feeds only, no fabricated metrics, no duplicated observability widgets. Emergency mutations stay on Ops."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/ops">Ops control</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/monitoring">Monitoring</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/terminal">Terminal</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/decision-intelligence">Decision Center</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <MissionControlWorkspace />
      </PageMotion>
    </div>
  );
}
