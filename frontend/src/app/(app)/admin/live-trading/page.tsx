"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { LiveTradingControlPanel } from "@/components/ops/live-trading-control-panel";

export default function LiveTradingAdminPage() {
  return (
    <div>
      <PageHeader
        eyebrow="Authorization"
        title="Live Trading"
        description="Controlled real-money authorization. Default DISABLED. ARM then ENABLE is required. Research cannot enable execution. Emergency stop disables new orders immediately and does not close existing positions."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/admin">Admin home</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/admin/live-trading-evidence">Evidence</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <LiveTradingControlPanel />
      </PageMotion>
    </div>
  );
}
