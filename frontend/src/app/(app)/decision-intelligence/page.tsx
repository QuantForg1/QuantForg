"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { DecisionIntelligenceWorkspace } from "@/components/ops/decision-intelligence-workspace";

export default function DecisionIntelligencePage() {
  return (
    <div>
      <PageHeader
        title="Decision Intelligence Center"
        description="Final institutional gate before execution. May REJECT or HOLD — never force-executes, never bypasses Risk Engine or Safety Engine, never places orders. Every decision is auditable."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/terminal">Terminal</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/institutional-decision">AI Decision</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/risk">Risk</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/market-intelligence">Market Intel</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <DecisionIntelligenceWorkspace />
      </PageMotion>
    </div>
  );
}
