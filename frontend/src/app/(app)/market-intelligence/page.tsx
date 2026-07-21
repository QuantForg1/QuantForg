"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { MarketIntelligenceWorkspace } from "@/components/ops/market-intelligence-workspace";

export default function MarketIntelligencePage() {
  return (
    <div>
      <PageHeader
        title="Market Intelligence Engine V1"
        description="Institutional pre-submit decision layer. Evaluates regime, consensus, opportunity rank, and risk dashboards from supplied analytics only — never invents market data, never bypasses Risk or Safety, never places orders."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/terminal">Terminal</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/institutional-decision">AI Decision</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/ai-robot">AI Robot</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/risk">Risk</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <MarketIntelligenceWorkspace />
      </PageMotion>
    </div>
  );
}
