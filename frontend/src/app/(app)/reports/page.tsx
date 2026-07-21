"use client";

import { FileText } from "lucide-react";
import { WorkspacePage } from "@/components/layout/workspace-page";

export default function ReportsPage() {
  return (
    <WorkspacePage
      title="Reports"
      description="Exportable performance and compliance reports from synced fills."
      icon={FileText}
      emptyTitle="Reports not generated"
      emptyDescription="Exportable reports build from live deal history and institutional analytics once fills sync."
      actionLabel="Open analytics"
      actionHref="/journal/analytics"
    />
  );
}
