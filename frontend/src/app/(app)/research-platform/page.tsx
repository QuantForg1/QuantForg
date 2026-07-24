"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { ResearchPlatformWorkspace } from "@/components/ops/research-platform-workspace";

export default function ResearchPlatformPage() {
  return (
    <div>
      <PageHeader
        title="Research Platform"
        description="v10 — Experiments, backtests, optimization, model registry, audit trail, and controlled promotion. Research stays isolated from live trading; never auto-deploy."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/portfolio-intelligence">Portfolio</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/performance-lab">Performance Lab</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/research">Research Desk</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <ResearchPlatformWorkspace />
      </PageMotion>
    </div>
  );
}
