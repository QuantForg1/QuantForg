"use client";

import { Workflow } from "lucide-react";
import { WorkspacePage } from "@/components/layout/workspace-page";

export default function IntegrationsPage() {
  return (
    <WorkspacePage
      title="Integrations"
      description="Connected brokers, data feeds, and platform services."
      icon={Workflow}
      emptyTitle="Manage integrations in Settings"
      emptyDescription="Broker connections, webhooks, and service integrations are configured in Settings."
      actionLabel="Open Settings"
      actionHref="/settings"
    />
  );
}
