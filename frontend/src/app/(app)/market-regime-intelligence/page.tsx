"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { MarketRegimeIntelligenceWorkspace } from "@/components/ops/market-regime-intelligence-workspace";

export default function MarketRegimeIntelligencePage() {
  return (
    <div>
      <PageHeader
        title="Market Regime Intelligence"
        description="Read-only classification of live evaluations — TRENDING, RANGING, BREAKOUT, PULLBACK, volatility, news, liquidity sweep — with history, distribution, and historical performance. Never influences execution."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/strategy-intelligence-center">
                Strategy Intelligence
              </Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/opportunity-timeline">Opportunity Timeline</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <MarketRegimeIntelligenceWorkspace />
      </PageMotion>
    </div>
  );
}
