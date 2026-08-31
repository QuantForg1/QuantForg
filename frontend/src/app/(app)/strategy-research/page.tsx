"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { StrategyResearchWorkspace } from "@/components/ops/strategy-research-workspace";

export default function StrategyResearchPage() {
  return (
    <div>
      <PageHeader
        title="Strategy Research"
        description="Read-only matched-trade forensics and shadow expansion. Never changes Opportunity 70, edge 5, Risk, Safety, or OMS. Unmatched broker deals are excluded. Tiny samples never display a win rate."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/strategy-intelligence-center">Strategy Intelligence</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/strategy-diagnostics">Diagnostics</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <StrategyResearchWorkspace />
      </PageMotion>
    </div>
  );
}
