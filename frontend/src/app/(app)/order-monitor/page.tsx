"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { OrderMonitorWorkspace } from "@/components/ops/order-monitor-workspace";

export default function OrderMonitorPage() {
  return (
    <div>
      <PageHeader
        title="Order Monitor"
        description="LIVE order lifecycle — Pending → Risk → OMS → Gateway → Broker → Accepted/Rejected → PME → Closed."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/orders">Orders</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/executions">Executions</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/execution/diagnostics">Diagnostics</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <OrderMonitorWorkspace />
      </PageMotion>
    </div>
  );
}
