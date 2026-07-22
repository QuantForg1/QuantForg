"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { IeeWorkspace } from "@/components/ops/iee-workspace";

export default function InstitutionalEdgeEnginePage() {
  return (
    <div>
      <PageHeader
        title="Institutional Edge Engine"
        description="Measure, validate, and explain QuantForg trading edge from completed trades. Advisory only — never fabricates metrics, never disables trading, never modifies Auto Trading / Execution / Decision / Risk / Safety / ASI."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/scalping-ai-v2">Scalping AI</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/adaptive-scalping-intelligence">ASI</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/terminal">Terminal</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <IeeWorkspace />
      </PageMotion>
    </div>
  );
}
