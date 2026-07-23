"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { AqcHistoryWorkspace } from "@/components/ops/aqc-workspaces";

export default function AqcHistoryPage() {
  return (
    <div>
      <PageHeader
        title="Conversation History"
        description="AQC-isolated conversation log — never writes production tables."
      />
      <PageMotion>
        <AqcHistoryWorkspace />
      </PageMotion>
    </div>
  );
}
