"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { ThresholdPromotionWorkspace } from "@/components/ops/threshold-promotion-workspace";

export default function ThresholdPromotionPage() {
  return (
    <div>
      <PageHeader
        title="Threshold Promotion"
        description="Controlled promotion of Quality/Confluence gates with explicit operator approval, versioned persistence, rollback to 80/80, and post-promotion monitoring. Never auto-promotes or auto-rollbacks."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/candidate-validation">Candidate Validation</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/threshold-performance-analysis">
                Threshold Performance
              </Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/auto-trading">Auto Trading</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <ThresholdPromotionWorkspace />
      </PageMotion>
    </div>
  );
}
