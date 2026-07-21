"use client";

import { ScanSearch } from "lucide-react";
import { WorkspacePage } from "@/components/layout/workspace-page";

export default function ScreenersPage() {
  return (
    <WorkspacePage
      title="Screeners"
      description="Symbol and strategy screeners from live research pipelines."
      icon={ScanSearch}
      emptyTitle="Screeners not connected"
      emptyDescription="Custom screeners attach when research data feeds are connected."
      actionLabel="Open Research"
      actionHref="/research"
    />
  );
}
