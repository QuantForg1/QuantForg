"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { QsmrRegistryWorkspace } from "@/components/ops/qsmr-workspaces";

export default function QuantForgStrategyMarketplacePage() {
  return (
    <div>
      <PageHeader
        title="Strategy Registry"
        description="QSMR — centralized strategy marketplace. Never modifies or deploys strategies."
      />
      <PageMotion>
        <QsmrRegistryWorkspace />
      </PageMotion>
    </div>
  );
}
