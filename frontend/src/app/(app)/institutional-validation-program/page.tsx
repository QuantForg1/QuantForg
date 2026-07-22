"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { InstitutionalValidationProgramWorkspace } from "@/components/ops/institutional-validation-program-workspace";

export default function InstitutionalValidationProgramPage() {
  return (
    <div>
      <PageHeader
        title="Institutional Validation Program"
        description="Read-only evidence framework. Continuously evaluates whether QuantForg has a statistically reliable edge before any production configuration change is considered. Never places trades. Never modifies strategies, execution, Risk, Safety, or Decision. Never auto-promotes research."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/institutional-edge-engine">Edge Engine</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/alpha-factory">Alpha Factory</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/terminal">Terminal</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <InstitutionalValidationProgramWorkspace />
      </PageMotion>
    </div>
  );
}
