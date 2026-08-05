"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { DeskSkeleton } from "@/components/desk/primitives";
import { Button } from "@/components/ui/button";
import { PlatformStatusBoard } from "@/components/ops/platform-status-board";
import { Rc2BurnInPanel } from "@/components/operator/rc2-burnin-panel";
import { MissionControlLatencyPlane } from "@/components/operator/mission-control-latency-plane";

const AutoRecoveryPanel = dynamic(
  () =>
    import("@/components/ops/auto-recovery-panel").then((m) => m.AutoRecoveryPanel),
  { loading: () => <DeskSkeleton rows={3} />, ssr: false },
);
const EventTimelinePanel = dynamic(
  () =>
    import("@/components/ops/event-timeline-panel").then((m) => m.EventTimelinePanel),
  { loading: () => <DeskSkeleton rows={4} />, ssr: false },
);
const MissionControlWorkspace = dynamic(
  () =>
    import("@/components/ops/mission-control-workspace").then(
      (m) => m.MissionControlWorkspace,
    ),
  { loading: () => <DeskSkeleton rows={6} />, ssr: false },
);

/** Production homepage — Mission Control + RC2 burn-in. */
export default function MissionControlPage() {
  return (
    <div>
      <PageHeader
        title="Mission Control"
        description="Production homepage — system status, burn-in telemetry, recovery, and LIVE event timeline. Trading Core untouched."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/terminal">Terminal</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/daily-reports">Reports</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/live-alerts">Alerts</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/trading-journal">Journal</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/production-burnin">Burn-in desk</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <div className="space-y-5">
          <PlatformStatusBoard />
          <MissionControlLatencyPlane />
          <Rc2BurnInPanel />
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
