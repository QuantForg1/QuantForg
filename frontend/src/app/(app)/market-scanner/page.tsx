"use client";

import { Radar } from "lucide-react";
import { WorkspacePage } from "@/components/layout/workspace-page";

export default function MarketScannerPage() {
  return (
    <WorkspacePage
      title="Market Scanner"
      description="Cross-market opportunity scan and regime filters."
      icon={Radar}
      emptyTitle="Scanner not connected"
      emptyDescription="Live scanner feeds attach through Research when macro and market data are connected."
      actionLabel="Open Research"
      actionHref="/research"
    />
  );
}
