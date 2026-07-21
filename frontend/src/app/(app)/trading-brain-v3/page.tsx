"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { TradingBrainV3Workspace } from "@/components/ops/trading-brain-v3-workspace";

export default function TradingBrainV3Page() {
  return (
    <div>
      <PageHeader
        title="Trading Brain V3"
        description="Highest-level orchestration for disciplined XAUUSD decision-making and capital preservation. Uses Decision Center, Risk, Safety, and Execution Pipeline — no alternate paths. May recommend No Trade. Never promises profitability."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/decision-intelligence">Decision Center</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/multi-agent-ai">Multi-Agent AI</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/terminal">Terminal</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <TradingBrainV3Workspace />
      </PageMotion>
    </div>
  );
}
