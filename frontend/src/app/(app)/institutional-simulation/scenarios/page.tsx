"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { IseScenariosWorkspace } from "@/components/ops/ise-workspaces";

export default function IseScenariosPage() {
  return (
    <div>
      <PageHeader
        title="Scenario Builder"
        description="Build isolated historical scenarios — spread, delay, volatility, sessions."
      />
      <PageMotion>
        <IseScenariosWorkspace />
      </PageMotion>
    </div>
  );
}
