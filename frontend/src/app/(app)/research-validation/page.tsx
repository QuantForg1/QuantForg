"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { ResearchValidationWorkspace } from "@/components/ops/research-validation-workspace";

export default function ResearchValidationPage() {
  return (
    <div>
      <PageHeader
        title="Research & Validation"
        description="Institutional environment where every XAUUSD strategy is validated before production. Reproducible results, traceable versions, mandatory certification, audit-preserving rollback. Live execution pipeline unchanged."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/strategy-lab">Strategy Lab</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/trading-brain-v3">Trading Brain</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/terminal">Terminal</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <ResearchValidationWorkspace />
      </PageMotion>
    </div>
  );
}
