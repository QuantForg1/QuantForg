"use client";

import { Suspense } from "react";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { DeskSkeleton } from "@/components/desk/primitives";
import { AiTradeReplayWorkspace } from "@/components/operator/ai-trade-replay-workspace";

export default function Page() {
  return (
    <div>
      <PageHeader
        title="AI Trade Replay"
        description="Animated Signal → Risk → OMS → Gateway → Broker → PME → Exit replay from LIVE audits."
      />
      <PageMotion>
        <Suspense fallback={<DeskSkeleton rows={6} />}>
          <AiTradeReplayWorkspace />
        </Suspense>
      </PageMotion>
    </div>
  );
}
