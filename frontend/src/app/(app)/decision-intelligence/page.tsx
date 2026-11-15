"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { DecisionIntelligenceWorkspace } from "@/components/ops/decision-intelligence-workspace";
import { Phase6DecisionDesk } from "@/components/ops/phase6/decision-desk";

export default function DecisionIntelligencePage() {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHeader
        eyebrow="Intelligence"
        title="Decision Intelligence"
        description="Unified advisory recommendations with explicit approval lifecycle — Approved never means LIVE."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/intelligence-center">Intelligence Center</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/ai-trading-intelligence">Phase 4 ATI</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/operations">Phase 5 Ops</Link>
            </Button>
          </div>
        }
      />
      <PageMotion className="min-h-0 flex-1 space-y-6 overflow-auto p-4">
        <Phase6DecisionDesk />
        <div className="border-t border-border/60 pt-4">
          <h2 className="mb-3 text-sm font-medium text-muted-foreground">
            Legacy Decision Center workspace
          </h2>
          <DecisionIntelligenceWorkspace />
        </div>
      </PageMotion>
    </div>
  );
}
