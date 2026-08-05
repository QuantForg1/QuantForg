"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { PortfolioIntelligenceWorkspace } from "@/components/ops/portfolio-intelligence-workspace";
import { IntelligencePortfolioDesk } from "@/components/operator/intelligence-portfolio-desk";

export default function PortfolioIntelligencePage() {
  return (
    <div>
      <PageHeader
        title="Portfolio Intelligence"
        description="LIVE equity, drawdown, allocation, and PnL attribution — plus advisory portfolio intelligence. No automatic capital reallocation."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/executive-home">Executive</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/performance-lab">Performance Lab</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/performance-analytics">Perf Analytics</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <div className="space-y-8">
          <IntelligencePortfolioDesk />
          <PortfolioIntelligenceWorkspace />
        </div>
      </PageMotion>
    </div>
  );
}
