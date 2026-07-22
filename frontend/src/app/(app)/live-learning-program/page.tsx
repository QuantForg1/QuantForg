"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { LiveLearningProgramWorkspace } from "@/components/ops/live-learning-program-workspace";

export default function LiveLearningProgramPage() {
  return (
    <div>
      <PageHeader
        title="Live Learning Program"
        description="Continuously collects evidence from live trading, paper, replay, and operator feedback to improve research quality. Never places trades, never modifies strategy rules, Risk, Safety, Decision, or Execution, never auto-tunes, never auto-promotes."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/institutional-validation-program">IVP</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/alpha-factory">Alpha Factory</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/terminal">Terminal</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <LiveLearningProgramWorkspace />
      </PageMotion>
    </div>
  );
}
