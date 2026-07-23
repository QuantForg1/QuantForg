"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { MicroAccountAnalyzerWorkspace } from "@/components/ops/micro-account-analyzer-workspace";

export default function MicroAccountAnalyzerPage() {
  return (
    <div>
      <PageHeader
        title="Micro Account Analyzer"
        description="Independent MICRO_ACCOUNT_MODE sizing for $50–$500 XAUUSD. Reads live broker min lot. Never weakens Institutional Mode (Q80/C80/1%). Never fakes lots."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/strategy-diagnostics">Strategy Diagnostics</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/auto-trading">Auto Trading</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <MicroAccountAnalyzerWorkspace />
      </PageMotion>
    </div>
  );
}
