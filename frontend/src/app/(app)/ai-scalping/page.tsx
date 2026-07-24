"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { AiScalpingWorkspace } from "@/components/ops/ai-scalping-workspace";

export default function AiScalpingPage() {
  return (
    <div>
      <PageHeader
        title="AI Scalping"
        description="v5 — Institutional H1/M15/M5/M1 scalping with balanced BUY/SELL, quality gates, structure stops, and 1–10m holds. Risk stays locked until quality improves."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/terminal">Terminal</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/performance-lab">Performance Lab</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/rc1">RC1</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <AiScalpingWorkspace />
      </PageMotion>
    </div>
  );
}
