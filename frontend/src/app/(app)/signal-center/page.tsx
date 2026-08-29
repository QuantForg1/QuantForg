"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { SignalCenterWorkspace } from "@/components/ops/signal-center-workspace";
import { Button } from "@/components/ui/button";

/** Operator gold-scan board. Trader Signals live at /signals. */
export default function SignalCenterPage() {
  return (
    <div>
      <PageHeader
        title="Signal Center"
        description="Operator view of the live XAUUSD scan. Trader market intelligence is on Signals."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/signals">Trader Signals</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/symbol-management">Symbol Management</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/admin">Admin</Link>
            </Button>
          </div>
        }
      />
      <SignalCenterWorkspace />
    </div>
  );
}
