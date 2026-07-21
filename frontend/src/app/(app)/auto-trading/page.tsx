"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { AutoTradingWorkspace } from "@/components/ops/auto-trading-workspace";

export default function AutoTradingPage() {
  return (
    <div>
      <PageHeader
        title="Auto Trading"
        description="Institutional command center for autonomous XAUUSD trading. Risk Engine and Safety Engine are never bypassed — all closes and submits use the production execution pipeline."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/terminal">Terminal</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/monitoring">Monitoring</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/ops">Ops</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <AutoTradingWorkspace />
      </PageMotion>
    </div>
  );
}
