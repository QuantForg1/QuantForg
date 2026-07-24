"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { AiValidationWorkspace } from "@/components/ops/ai-validation-workspace";

export default function AiValidationPage() {
  return (
    <div>
      <PageHeader
        title="AI Validation"
        description="v7 — Shadow AI comparisons, strategy performance, execution quality, slippage, weight optimizer, opportunity replay. Observational optimization; trading rules and safeguards unchanged."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/production-reliability">Reliability</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/auto-trading">Auto Trading</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/institutional-alpha">Alpha</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <AiValidationWorkspace />
      </PageMotion>
    </div>
  );
}
