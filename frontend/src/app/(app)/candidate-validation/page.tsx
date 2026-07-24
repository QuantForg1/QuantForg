"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { CandidateValidationWorkspace } from "@/components/ops/candidate-validation-workspace";

export default function CandidateValidationPage() {
  return (
    <div>
      <PageHeader
        title="Candidate Validation"
        description="Offline A/B: production Q80/C80 vs candidate Q70/C75 on the same 90-day XAUUSD replay. Never modifies production thresholds or engines."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/threshold-performance-analysis">
                Threshold Performance
              </Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/research">Research</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <CandidateValidationWorkspace />
      </PageMotion>
    </div>
  );
}
