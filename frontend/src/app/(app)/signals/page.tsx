"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { SignalCenterWorkspace } from "@/components/ops/signal-center-workspace";
import { Button } from "@/components/ui/button";

export default function SignalsPage() {
  return (
    <div>
      <PageHeader
        title="Signal Center"
        description="LIVE institutional signals from the XAUUSD (Gold) scan. Never fabricated. Auto-refreshes without page reload."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/symbol-management">Symbol Management</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/admin/noc">NOC</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/ai-signals">Counsel</Link>
            </Button>
          </div>
        }
      />
      <SignalCenterWorkspace />
    </div>
  );
}
