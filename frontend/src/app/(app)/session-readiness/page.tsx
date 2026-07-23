"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { SessionReadinessWorkspace } from "@/components/ops/session-readiness-workspace";

export default function SessionReadinessPage() {
  return (
    <div>
      <PageHeader
        title="Session Readiness"
        description="Read-only session gate view — current/next allowed session and live execution-window counters. Never modifies trading logic."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/production-acceptance-countdown">Countdown</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/auto-trading">Trading Ops</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/production-validation">Validation</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <SessionReadinessWorkspace />
      </PageMotion>
    </div>
  );
}
