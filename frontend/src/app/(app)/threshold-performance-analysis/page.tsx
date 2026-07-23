"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { ThresholdPerformanceWorkspace } from "@/components/ops/threshold-performance-workspace";

export default function ThresholdPerformanceAnalysisPage() {
  return (
    <div>
      <PageHeader
        title="Threshold Performance Analysis"
        description="Offline Research desk: independent Quality × Confluence gate replays on XAUUSD (last 90 days). Statistics, rankings, heatmap, and exports only — never modifies strategy, risk, safety, OMS, MT5, or live thresholds."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/research">Research</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/strategy-diagnostics">Strategy Diagnostics</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/strategy-lab">Strategy Lab</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <ThresholdPerformanceWorkspace />
      </PageMotion>
    </div>
  );
}
