"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { IrapDrawdownWorkspace } from "@/components/ops/irap-workspaces";

export default function IrapDrawdownPage() {
  return (
    <div>
      <PageHeader
        title="Drawdown Explorer"
        description="Maximum, current drawdown, ulcer index and trend."
      />
      <PageMotion>
        <IrapDrawdownWorkspace />
      </PageMotion>
    </div>
  );
}
