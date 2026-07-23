"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { QkgRootCauseWorkspace } from "@/components/ops/qkg-workspaces";

export default function QkgRootCausePage() {
  return (
    <div>
      <PageHeader
        title="Root Cause Explorer"
        description="Upstream cause ranking across diagnostics, risk, safety, and alerts."
      />
      <PageMotion>
        <QkgRootCauseWorkspace />
      </PageMotion>
    </div>
  );
}
