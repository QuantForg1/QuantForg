"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { IntelligencePlatformWorkspace } from "@/components/ops/intelligence-platform-workspace";

export default function IntelligencePlatformPage() {
  return (
    <div>
      <PageHeader
        title="Intelligence Platform"
        description="Institutional research and continuous improvement. Replay and reports use recorded data only — never sends broker orders, never affects production execution, never fabricates metrics."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/research">Research OS</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/strategy-lab">Strategy Lab</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/trade-replay">Trade Replay</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/decision-intelligence">Decision Center</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <IntelligencePlatformWorkspace />
      </PageMotion>
    </div>
  );
}
