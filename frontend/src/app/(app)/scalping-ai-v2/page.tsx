"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { ScalpingAiV2Workspace } from "@/components/ops/scalping-ai-v2-workspace";

export default function ScalpingAiV2Page() {
  return (
    <div>
      <PageHeader
        title="Scalping AI V2"
        description="Institutional XAUUSD scalping orchestration — continuous, recoverable, capital-preserving. Never bypasses Risk, Safety, or Decision Center. Prefers No Trade. Never order_send."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/auto-trading">Auto Trading</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/decision-intelligence">Decision Center</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/terminal">Terminal</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <ScalpingAiV2Workspace />
      </PageMotion>
    </div>
  );
}
