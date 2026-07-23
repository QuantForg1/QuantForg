"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { EqsBrokerWorkspace } from "@/components/ops/eqs-workspaces";

export default function EqsBrokerPage() {
  return (
    <div>
      <PageHeader
        title="Broker Health"
        description="Uptime, response latency, failures, reconnects, health score."
      />
      <PageMotion>
        <EqsBrokerWorkspace />
      </PageMotion>
    </div>
  );
}
