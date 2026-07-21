"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { StrategyLabWorkspace } from "@/components/ops/strategy-lab-workspace";

export default function StrategyLabPage() {
  return (
    <div>
      <PageHeader
        title="Strategy Research Lab"
        description="Institutional environment to validate and promote strategies before production. Completely separated from live execution — never submits broker orders, never affects production positions, never invents production metrics."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/research">Research</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/research-lab">Research Lab</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/decision-engine">Decision Engine</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/terminal">Terminal</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <StrategyLabWorkspace />
      </PageMotion>
    </div>
  );
}
