"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { AlphaFactoryWorkspace } from "@/components/ops/alpha-factory-workspace";

export default function AlphaFactoryPage() {
  return (
    <div>
      <PageHeader
        title="Alpha Factory"
        description="Isolated research environment to discover, validate, compare, and stage trading ideas. Never modifies live strategy, Risk, Safety, Decision, Execution, or Auto Trading. Never auto-promotes."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/strategy-lab">Strategy Lab</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/institutional-edge-engine">Edge Engine</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/terminal">Terminal</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <AlphaFactoryWorkspace />
      </PageMotion>
    </div>
  );
}
