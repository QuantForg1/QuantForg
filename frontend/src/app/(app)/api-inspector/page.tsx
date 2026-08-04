"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { ApiInspectorWorkspace } from "@/components/ops/api-inspector-workspace";

export default function ApiInspectorPage() {
  return (
    <div>
      <PageHeader
        title="API Inspector"
        description="Client-side LIVE telemetry from apiFetch — route, method, status, latency, size, retries, timeouts. Never fabricated."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/mission-control">Mission Control</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/logs">Logs</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/monitoring">Monitoring</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <ApiInspectorWorkspace />
      </PageMotion>
    </div>
  );
}
