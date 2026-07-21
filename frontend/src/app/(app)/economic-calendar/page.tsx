"use client";

import { Calendar } from "lucide-react";
import { WorkspacePage } from "@/components/layout/workspace-page";

export default function EconomicCalendarPage() {
  return (
    <WorkspacePage
      title="Economic Calendar"
      description="Macro event schedule and impact windows."
      icon={Calendar}
      emptyTitle="Calendar not connected"
      emptyDescription="Economic calendar attaches when macro feed is connected."
      actionLabel="Open Research"
      actionHref="/research"
    />
  );
}
