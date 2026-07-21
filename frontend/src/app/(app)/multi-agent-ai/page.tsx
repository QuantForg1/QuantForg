"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { MultiAgentAiWorkspace } from "@/components/ops/multi-agent-ai-workspace";

export default function MultiAgentAiPage() {
  return (
    <div>
      <PageHeader
        title="Multi-Agent AI"
        description="Independent institutional agents collaborate on XAUUSD before any trade is approved. Risk and Safety remain authoritative. Coordinator may reject — never bypasses. AI Memory stores observations only."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/decision-intelligence">Decision Center</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/trading-kernel">Trading Kernel</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/terminal">Terminal</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <MultiAgentAiWorkspace />
      </PageMotion>
    </div>
  );
}
