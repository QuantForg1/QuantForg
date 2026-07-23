"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { ProductionAcceptanceTestWorkspace } from "@/components/ops/production-acceptance-test-workspace";

export default function ProductionAcceptanceTestPage() {
  return (
    <div>
      <PageHeader
        title="Production Acceptance Test"
        description="Read-only PAT for the first successful end-to-end live fill. Evidence-only checklist across Market, Decision, Risk, Safety, Execution, Trade, and Audit. No manual approval. Never modifies trading logic."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/automatic-production-acceptance">Auto Acceptance</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/first-execution-evidence">First Evidence</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/production-acceptance">Acceptance Desk</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <ProductionAcceptanceTestWorkspace />
      </PageMotion>
    </div>
  );
}
