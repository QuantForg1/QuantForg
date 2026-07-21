"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { TradingKernelWorkspace } from "@/components/ops/trading-kernel-workspace";

export default function TradingKernelPage() {
  return (
    <div>
      <PageHeader
        title="Trading Kernel V1"
        description="Core OS that orchestrates production trading components for XAUUSD. Event bus, state machine, policies, plugins, decision graph, and deterministic replay — never bypasses Risk or Safety, never changes Execution Pipeline, never order_send."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/decision-intelligence">Decision Center</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/production-readiness">Readiness</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/terminal">Terminal</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <TradingKernelWorkspace />
      </PageMotion>
    </div>
  );
}
