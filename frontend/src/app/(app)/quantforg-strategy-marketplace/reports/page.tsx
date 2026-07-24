"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { QsmrReportsWorkspace } from "@/components/ops/qsmr-workspaces";

export default function QsmrReportsPage() {
  return (
    <div>
      <PageHeader
        title="Registry Reports"
        description="Strategy registry, portfolio, certification and version reports — read-only."
      />
      <PageMotion>
        <QsmrReportsWorkspace />
      </PageMotion>
    </div>
  );
}
