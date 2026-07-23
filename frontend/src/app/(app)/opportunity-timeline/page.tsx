"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { OpportunityTimelineWorkspace } from "@/components/ops/opportunity-timeline-workspace";

export default function OpportunityTimelinePage() {
  return (
    <div>
      <PageHeader
        title="Opportunity Timeline"
        description="Live history of the last 100 evaluations — MTF, Quality, Confluence, Risk Lots, Opportunity Meter — with trend charts and Approaching / Weakening / Stable prediction. Read-only."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/adaptive-opportunity">Adaptive Opportunity</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/live-execution-explain">Live Execution Explain</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <OpportunityTimelineWorkspace />
      </PageMotion>
    </div>
  );
}
