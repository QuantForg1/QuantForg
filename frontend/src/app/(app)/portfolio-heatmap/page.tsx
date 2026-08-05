"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { PortfolioHeatmapWorkspace } from "@/components/operator/portfolio-heatmap-workspace";

export default function Page() {
  return (
    <div>
      <PageHeader
        title="Portfolio Heatmap"
        description="Realtime Forex / Crypto / Metals / Indices / Energy exposure from LIVE positions."
      />
      <PageMotion>
        <PortfolioHeatmapWorkspace />
      </PageMotion>
    </div>
  );
}
