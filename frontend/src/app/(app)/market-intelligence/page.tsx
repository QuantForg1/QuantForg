"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { MarketIntelligenceWorkspace } from "@/components/ops/market-intelligence-workspace";
import { MarketIntelligenceRc3Panel } from "@/components/operator/market-intelligence-rc3-panel";
import { GlobalMarketUniverseWorkspace } from "@/components/ops/global-market-universe-workspace";

export default function MarketIntelligencePage() {
  return (
    <div>
      <PageHeader
        title="Market Intelligence"
        description="LIVE heat map, breadth, and the global multi-asset research universe. Advisory only. Never invents market data. Never places orders."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/signals">Signal Center</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/ai-coach">AI Coach</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/terminal">Terminal</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <div className="space-y-8">
          <GlobalMarketUniverseWorkspace />
          <MarketIntelligenceRc3Panel />
          <MarketIntelligenceWorkspace />
        </div>
      </PageMotion>
    </div>
  );
}
