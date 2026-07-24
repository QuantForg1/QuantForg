"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { PortfolioIntelligenceWorkspace } from "@/components/ops/portfolio-intelligence-workspace";

export default function PortfolioIntelligencePage() {
  return (
    <div>
      <PageHeader
        title="Portfolio Intelligence"
        description="v9 — AI Portfolio Manager: risk budget, capital allocation, opportunity queue, stress tests, global regime, and advisory recommendations. No automatic capital reallocation."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/performance-lab">Performance Lab</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/institutional-alpha">Alpha</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/auto-trading">Auto Trading</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <PortfolioIntelligenceWorkspace />
      </PageMotion>
    </div>
  );
}
