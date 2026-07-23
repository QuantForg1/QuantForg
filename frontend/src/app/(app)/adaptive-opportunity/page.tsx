"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { AdaptiveOpportunityWorkspace } from "@/components/ops/adaptive-opportunity-workspace";

export default function AdaptiveOpportunityPage() {
  return (
    <div>
      <PageHeader
        title="Adaptive Opportunity"
        description="When NO TRADE, shows exactly what is missing — MTF, Quality, Confluence, Risk equity gap — plus Opportunity Meter and historical wait estimates. Strategy and thresholds unchanged."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/live-execution-explain">Live Execution Explain</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/strategy-diagnostics">Strategy Diagnostics</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <AdaptiveOpportunityWorkspace />
      </PageMotion>
    </div>
  );
}
