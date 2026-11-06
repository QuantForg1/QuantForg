"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { StrategyPerformanceDashboardWorkspace } from "@/components/ops/strategy-performance-dashboard-workspace";

export default function StrategyPerformancePage() {
  return (
    <div>
      <PageHeader
        title="Strategy Performance"
        description="Broker-confirmed five-pack scorecards, BUY/SELL breakdown, capital protection, and attribution quality. Observation only — never mutates risk, cascades, OMS, or LIVE submit."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/strategy-diagnostics">Diagnostics</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/admin">Admin</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/performance-intelligence">Performance IQ</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <StrategyPerformanceDashboardWorkspace />
      </PageMotion>
    </div>
  );
}
