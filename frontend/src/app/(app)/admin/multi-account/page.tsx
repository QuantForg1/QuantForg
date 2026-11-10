"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { MultiAccountOpsWorkspace } from "@/components/ops/multi-account-ops-workspace";

export default function AdminMultiAccountOpsPage() {
  return (
    <div>
      <PageHeader
        title="Multi-Account Operations"
        description="Read-only dispatch queue and worker telemetry. RC4 charcoal · observe-only · never enqueues jobs or enables LIVE multi-account submit."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/admin/noc">NOC</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/admin/control">Owner control</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/admin/live-trading">Live trading</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <MultiAccountOpsWorkspace />
      </PageMotion>
    </div>
  );
}
