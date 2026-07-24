"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { IcpHealthWorkspace } from "@/components/ops/icp-workspaces";

export default function IcpHealthPage() {
  return (
    <div>
      <PageHeader
        title="Health Center"
        description="Executive health scores across trading, execution, reliability, risk and more."
      />
      <PageMotion>
        <IcpHealthWorkspace />
      </PageMotion>
    </div>
  );
}
