"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { RealMarketIntelligencePlatformWorkspace } from "@/components/ops/real-market-intelligence-platform-workspace";

export default function RealMarketIntelligencePlatformPage() {
  return (
    <div>
      <PageHeader
        title="Real Market Intelligence Platform"
        description="Institutional intelligence layer that enriches market context from real-world information. Context only — never places trades, never changes trading rules, and never modifies Auto Trading, Execution, Decision, Risk, Safety, ASI, Edge Engine, Alpha Factory, or IVP."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/market-intelligence">Market Intelligence</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/institutional-validation-program">IVP</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/terminal">Terminal</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <RealMarketIntelligencePlatformWorkspace />
      </PageMotion>
    </div>
  );
}
