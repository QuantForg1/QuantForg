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
        title="AI Trading Robot V1"
        description="Institutional capital-preservation module. Discipline first — never promises profitability. Risk Engine and Safety Engine are never bypassed; Robot V1 does not place orders."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/terminal">Terminal</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/auto-trading">Auto Trading</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/risk">Risk</Link>
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
