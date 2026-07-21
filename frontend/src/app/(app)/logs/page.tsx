"use client";

import { BookOpen } from "lucide-react";
import { WorkspacePage } from "@/components/layout/workspace-page";

/** Operations logs — streams when observability is connected. */
export default function LogsPage() {
  return (
    <WorkspacePage
      title="Logs"
      description="Operational log stream for gateway, execution, and recovery events."
      icon={BookOpen}
      emptyTitle="No log stream attached"
      emptyDescription="Operational logs appear when observability is connected. Use Monitoring for live health."
      actionLabel="Open Monitoring"
      actionHref="/monitoring"
    />
  );
}
