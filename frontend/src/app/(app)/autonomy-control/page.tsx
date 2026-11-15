"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Phase7ControlDesk } from "@/components/ops/phase7/control-desk";

export default function AutonomyControlPage() {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHeader
        eyebrow="Autonomy"
        title="Autonomy Control"
        description="Explicit operating modes. Default OBSERVE_ONLY. Mode changes are audited and never silently enable LIVE."
      />
      <PageMotion className="min-h-0 flex-1 overflow-auto p-4">
        <Phase7ControlDesk />
      </PageMotion>
    </div>
  );
}
