"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { QsmrExplorerWorkspace } from "@/components/ops/qsmr-workspaces";

export default function QsmrExplorerPage() {
  return (
    <div>
      <PageHeader
        title="Strategy Explorer"
        description="Search, filter, sort and group strategies — read-only discovery."
      />
      <PageMotion>
        <QsmrExplorerWorkspace />
      </PageMotion>
    </div>
  );
}
