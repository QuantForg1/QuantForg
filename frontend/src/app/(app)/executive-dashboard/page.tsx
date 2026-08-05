"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { ExecutiveHomeWorkspace } from "@/components/operator/executive-home-workspace";
import { PortfolioHeatmapWorkspace } from "@/components/operator/portfolio-heatmap-workspace";

export default function ExecutiveDashboardPage() {
  return (
    <div>
      <PageHeader
        title="Executive Home"
        description="CEO intelligence desk — LIVE capital, performance, signals, risk, and system health. Never fabricated."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/mission-control">Mission Control</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/portfolio-intelligence">Portfolio Intel</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/daily-reports">Reports</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/ai-coach">AI Coach</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <div className="space-y-6">
          <ExecutiveHomeWorkspace />
          <section className="space-y-2">
            <h2 className="text-[12px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
              Portfolio heatmap
            </h2>
            <PortfolioHeatmapWorkspace />
          </section>
        </div>
      </PageMotion>
    </div>
  );
}
