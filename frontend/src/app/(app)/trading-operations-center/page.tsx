"use client";

import { ClipboardCheck } from "lucide-react";
import { WorkspacePage } from "@/components/layout/workspace-page";
import { TradingOperationsCenterWorkspace } from "@/components/ops/trading-operations-center-workspace";

export default function TradingOperationsCenterPage() {
  return (
    <WorkspacePage
      title="Trading Operations Center"
      description="Daily brief, readiness checklist, EOD/weekly/monthly reviews, and ops alerts — advisory only; never modifies strategy, risk, safety, execution, Performance IQ, or Evidence Lab."
      icon={ClipboardCheck}
      actionLabel="Auto Trading"
      actionHref="/auto-trading"
    >
      <TradingOperationsCenterWorkspace />
    </WorkspacePage>
  );
}
