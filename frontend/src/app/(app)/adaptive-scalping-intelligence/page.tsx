"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { AsiWorkspace } from "@/components/ops/asi-workspace";

export default function AdaptiveScalpingIntelligencePage() {
  return (
    <div>
      <PageHeader
        title="Adaptive Scalping Intelligence"
        description="XAUUSD adaptive market intelligence and explainability. Learns only from supplied historical observations. Never fabricates stats, never auto-modifies rules, never order_send."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/scalping-ai-v2">Scalping AI V2</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/decision-intelligence">Decision Center</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/terminal">Terminal</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <AsiWorkspace />
      </PageMotion>
    </div>
  );
}
