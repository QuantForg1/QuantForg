"use client";

import { BarChart3 } from "lucide-react";
import { WorkspacePage } from "@/components/layout/workspace-page";
import { PerformanceIntelligenceWorkspace } from "@/components/ops/performance-intelligence-workspace";

export default function PerformanceIntelligencePage() {
  return (
    <WorkspacePage
      title="Performance Intelligence"
      description="Institutional analytics from execution journals only — never modifies strategy, risk, safety, or execution."
      icon={BarChart3}
      actionLabel="Reports"
      actionHref="/reports"
    >
      <PerformanceIntelligenceWorkspace />
    </WorkspacePage>
  );
}
