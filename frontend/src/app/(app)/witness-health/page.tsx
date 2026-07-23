"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { WitnessHealthWorkspace } from "@/components/ops/witness-health-workspace";

export default function WitnessHealthPage() {
  return (
    <div>
      <PageHeader
        title="Witness Health"
        description="Separates witness authentication health from trading execution health. HTTP 401 shows as Witness Authentication Failed — never as an execution failure. Does not alter Production Acceptance."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/production-acceptance">Acceptance</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/production-reliability">Reliability</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/monitoring">Monitoring</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <WitnessHealthWorkspace />
      </PageMotion>
    </div>
  );
}
