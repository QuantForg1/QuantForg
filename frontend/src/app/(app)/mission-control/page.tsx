"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { MissionControlWorkspace } from "@/components/ops/mission-control-workspace";
import { PlatformStatusBoard } from "@/components/ops/platform-status-board";

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
              <Link href="/monitoring">Monitoring</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/terminal">Terminal</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/broker">Broker</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <div className="space-y-6">
          <PlatformStatusBoard />
          <MissionControlWorkspace />
        </div>
      </PageMotion>
    </div>
  );
}
