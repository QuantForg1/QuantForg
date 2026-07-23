"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { PortfolioAnalyticsWorkspace } from "@/components/ops/portfolio-analytics-workspace";

export default function PortfolioAnalyticsPage() {
  return (
    <div>
      <PageHeader
        title="Institutional Portfolio Analytics"
        description="Read-only MT5 portfolio intelligence — dashboard, risk, performance, behavior, and equity curves from closed XAUUSD trades. Never modifies strategy, risk, OMS, or execution."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/strategy-intelligence-center">
                Strategy Intelligence
              </Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/market-regime-intelligence">Market Regime</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <PortfolioAnalyticsWorkspace />
      </PageMotion>
    </div>
  );
}
