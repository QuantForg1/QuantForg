"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { ContinuousImprovementProgram } from "@/components/ops/continuous-improvement-program";

export default function ContinuousImprovementAdminPage() {
  return (
    <div>
      <PageHeader
        title="Continuous Improvement"
        description="Live validation, trading effectiveness, learning review, release confidence, scorecard, and trends — production evidence only. Never modifies trading, AI, OMS, MT5, auth, or pricing."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/admin/noc">NOC</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/admin/reliability">Reliability</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/admin/enterprise">Enterprise</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <ContinuousImprovementProgram />
      </PageMotion>
    </div>
  );
}
