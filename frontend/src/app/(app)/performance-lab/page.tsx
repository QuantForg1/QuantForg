"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { PerformanceLabWorkspace } from "@/components/ops/performance-lab-workspace";

export default function PerformanceLabPage() {
  return (
    <div>
      <PageHeader
        title="Performance Lab"
        description="v8 — Champion vs Challenger (challenger never executes), confidence calibration, trade replay, strategy comparison, portfolio heatmap, symbol rankings, and advisory recommendations only."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/ai-validation">AI Validation</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/production-reliability">Reliability</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/auto-trading">Auto Trading</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <PerformanceLabWorkspace />
      </PageMotion>
    </div>
  );
}
