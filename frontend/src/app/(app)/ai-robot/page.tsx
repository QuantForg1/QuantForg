"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { AiRobotWorkspace } from "@/components/ops/ai-robot-workspace";

export default function AiRobotPage() {
  return (
    <div>
      <PageHeader
        eyebrow="Robot Desk"
        title="AI Trading Robot V1"
        description="Capital-preservation discipline module. Process running is not a signal, not authorization, and not a broker-confirmed fill. Risk and Safety engines are never bypassed; this desk does not invent executions."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/terminal">Terminal</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/auto-trading">Auto Trading</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/risk-center">Risk Center</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <AiRobotWorkspace />
      </PageMotion>
    </div>
  );
}
