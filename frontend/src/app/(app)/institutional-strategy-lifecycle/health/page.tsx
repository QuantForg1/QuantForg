"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { IslmHealthWorkspace } from "@/components/ops/islm-workspaces";

export default function IslmHealthPage() {
  return (
    <div>
      <PageHeader
        title="Strategy Health"
        description="Research, validation, execution, reliability and risk scores — advisory only."
      />
      <PageMotion>
        <IslmHealthWorkspace />
      </PageMotion>
    </div>
  );
}
