"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { ExperimentalThresholdWorkspace } from "@/components/ops/experimental-threshold-workspace";

export default function ExperimentalThresholdPage() {
  return (
    <div>
      <PageHeader
        title="Experimental Threshold Profile"
        description="Temporary EXPERIMENTAL_75 (Q75/C75) overlay. Institutional DEFAULT stays Q80/C80. Explicit activation, audit log, one-click rollback. Never auto-promotes."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/threshold-promotion">Threshold Promotion</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/strategy-diagnostics">Strategy Diagnostics</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <ExperimentalThresholdWorkspace />
      </PageMotion>
    </div>
  );
}
