"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { EqsLatencyWorkspace } from "@/components/ops/eqs-workspaces";

export default function EqsLatencyPage() {
  return (
    <div>
      <PageHeader
        title="Latency Explorer"
        description="Strategy, OMS, gateway, broker, fill, and total execution latency."
      />
      <PageMotion>
        <EqsLatencyWorkspace />
      </PageMotion>
    </div>
  );
}
