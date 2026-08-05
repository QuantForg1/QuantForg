"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { OperatorHomeWorkspace } from "@/components/operator/operator-home-workspace";

export default function Page() {
  return (
    <div>
      <PageHeader
        title="Operator Home"
        description="Mission Control brief — today performance, signals, orders, risk, AI advice."
      />
      <PageMotion>
        <OperatorHomeWorkspace />
      </PageMotion>
    </div>
  );
}
