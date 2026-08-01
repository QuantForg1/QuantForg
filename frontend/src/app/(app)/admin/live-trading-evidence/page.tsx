"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { LiveTradingEvidenceProgram } from "@/components/ops/live-trading-evidence-program";

export default function LiveTradingEvidenceAdminPage() {
  return (
    <div>
      <PageHeader
        title="Live Trading Evidence"
        description="Trade evidence repository, investigation console, rejected opportunities, evidence dashboard, and production readiness — real production evidence only. Never forces trades or changes AI/strategy."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/admin/noc">NOC</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/admin/continuous-improvement">CI</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/live-execution-explain">Execution Explain</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <LiveTradingEvidenceProgram />
      </PageMotion>
    </div>
  );
}
