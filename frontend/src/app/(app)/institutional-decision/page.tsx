"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { InstitutionalDecisionWorkspace } from "@/components/ops/institutional-decision-workspace";

export default function InstitutionalDecisionPage() {
  return (
    <div>
      <PageHeader
        title="Institutional AI Decision Engine V1"
        description="Multi-layer capital-preservation decisions. Dry-run validates signals without orders. Risk Engine and Safety Engine are never bypassed — profitability is never promised."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/terminal">Terminal</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/ai-robot">AI Robot</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/decision-engine">Decision Engine</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/risk">Risk</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <InstitutionalDecisionWorkspace />
      </PageMotion>
    </div>
  );
}
