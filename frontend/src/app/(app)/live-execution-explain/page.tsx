"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { LiveExecutionExplainWorkspace } from "@/components/ops/live-execution-explain-workspace";

export default function LiveExecutionExplainPage() {
  return (
    <div>
      <PageHeader
        title="Live Execution Explain"
        description="One decision card per live evaluation. EXECUTE TRADE shows every PASS reason. NO TRADE shows only the first blocking condition. Engines unchanged."
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
        <LiveExecutionExplainWorkspace />
      </PageMotion>
    </div>
  );
}
