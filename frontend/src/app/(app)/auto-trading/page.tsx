"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { AutoTradingWorkspace } from "@/components/ops/auto-trading-workspace";
import { WorkspaceShell } from "@/components/workspace/shell";

export default function AutoTradingPage() {
  return (
    <div>
      <PageHeader
        title="Trading Operations Center"
        description="Live market, strategy bias, risk, and the execution pipeline. Existing safety controls stay in place."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/dashboard">Dashboard</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/monitoring">Monitoring</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/ops">Ops</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <section
          aria-label="Trading terminal"
          className="mb-4 overflow-hidden rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--bg)] lg:flex lg:h-[min(960px,calc(100dvh-7.5rem))] lg:flex-col"
        >
          <div className="min-h-0 lg:h-full lg:min-h-0 lg:flex-1">
            <WorkspaceShell captureHotkeys={false} />
          </div>
        </section>
        <AutoTradingWorkspace />
      </PageMotion>
    </div>
  );
}
