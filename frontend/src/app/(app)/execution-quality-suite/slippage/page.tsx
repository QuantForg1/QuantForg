"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { EqsSlippageWorkspace } from "@/components/ops/eqs-workspaces";

export default function EqsSlippagePage() {
  return (
    <div>
      <PageHeader
        title="Slippage Explorer"
        description="Expected vs actual entry/exit and slippage distribution."
      />
      <PageMotion>
        <EqsSlippageWorkspace />
      </PageMotion>
    </div>
  );
}
