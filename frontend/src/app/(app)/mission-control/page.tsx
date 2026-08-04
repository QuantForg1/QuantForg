"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { MissionControlWorkspace } from "@/components/ops/mission-control-workspace";
import { PlatformStatusBoard } from "@/components/ops/platform-status-board";
import { EventTimelinePanel } from "@/components/ops/event-timeline-panel";
import { AutoRecoveryPanel } from "@/components/ops/auto-recovery-panel";

export default function MissionControlPage() {
  return (
    <div>
      <PageHeader
        title="Mission Control"
        description="Independent production status planes — Backend, Gateway, MT5, Broker, and Session never collapse into one Offline bit. Live feeds only."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/ops">Ops control</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/api-inspector">API Inspector</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/order-monitor">Order Monitor</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/terminal">Terminal</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <div className="space-y-6">
          <PlatformStatusBoard />
          <AutoRecoveryPanel />
          <section className="space-y-3">
            <h2 className="text-[12px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
              Event timeline
            </h2>
            <EventTimelinePanel />
          </section>
          <MissionControlWorkspace />
        </div>
      </PageMotion>
    </div>
  );
}
