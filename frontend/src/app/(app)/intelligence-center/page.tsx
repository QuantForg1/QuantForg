"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Phase6HubDesk } from "@/components/ops/phase6/hub-desk";

export default function IntelligenceCenterPage() {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHeader
        eyebrow="Intelligence"
        title="Intelligence Center"
        description="Unified hub for predictive market, strategy, risk, portfolio, execution, decisions and reports."
      />
      <PageMotion className="min-h-0 flex-1 overflow-auto p-4">
        <Phase6HubDesk />
      </PageMotion>
    </div>
  );
}
