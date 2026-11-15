"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Phase8HubDesk } from "@/components/ops/phase8/hub-desk";

export default function QuantResearchPage() {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHeader
        eyebrow="Research Factory"
        title="Quant Research"
        description="Projects and experiments hub — research-only, never order_send, never auto LIVE deploy."
      />
      <PageMotion className="min-h-0 flex-1 overflow-auto p-4">
        <Phase8HubDesk />
      </PageMotion>
    </div>
  );
}
