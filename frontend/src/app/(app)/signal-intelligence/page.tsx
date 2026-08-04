"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { SignalIntelligenceWorkspace } from "@/components/ops/signal-intelligence-workspace";
import { Button } from "@/components/ui/button";

export default function SignalIntelligencePage() {
  return (
    <div>
      <PageHeader
        title="Signal Intelligence v2"
        description="LIVE signal history, outcomes, probability, heat map, chart overlay, and per-symbol analytics from real MT5 closes — never fabricated."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/signals">Signal Center</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/symbol-management">Symbol Management</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/admin/noc">NOC</Link>
            </Button>
          </div>
        }
      />
      <SignalIntelligenceWorkspace />
    </div>
  );
}
