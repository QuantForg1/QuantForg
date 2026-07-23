"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { StrategyIntelligenceCenterWorkspace } from "@/components/ops/strategy-intelligence-center-workspace";

export default function StrategyIntelligenceCenterPage() {
  return (
    <div>
      <PageHeader
        title="Strategy Intelligence Center"
        description="Read-only analysis of completed trades — sessions, regimes, patterns, and a 0–100 score of whether current conditions resemble historically profitable setups. Never changes strategy or thresholds."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/adaptive-opportunity">Adaptive Opportunity</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/opportunity-timeline">Opportunity Timeline</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <StrategyIntelligenceCenterWorkspace />
      </PageMotion>
    </div>
  );
}
