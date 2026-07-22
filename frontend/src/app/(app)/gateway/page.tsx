"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { WeltradeGatewayStatus } from "@/components/desk/weltrade-gateway-status";
import { ExecutionStateStrip } from "@/components/ops/execution-state-strip";
import {
  EMPTY_EXECUTION_METRICS,
  ExecutionMetricsStrip,
  type ExecutionTimingMetrics,
} from "@/components/execution/execution-metrics-strip";
import { loadLastExecutionMetrics } from "@/lib/execution/last-metrics";
import { mt5Api, platformApi } from "@/lib/api/endpoints";

export default function GatewayPage() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: platformApi.health,
    retry: false,
    refetchInterval: 30_000,
  });
  const mt5 = useQuery({
    queryKey: ["mt5-status"],
    queryFn: mt5Api.status,
    retry: false,
    refetchInterval: 30_000,
  });

  const [execMetrics, setExecMetrics] = useState<ExecutionTimingMetrics>(
    EMPTY_EXECUTION_METRICS,
  );
  useEffect(() => {
    setExecMetrics(loadLastExecutionMetrics());
  }, [health.dataUpdatedAt, mt5.dataUpdatedAt]);

  return (
    <div>
      <PageHeader
        title="Gateway"
        description="Execution gateway health and latency — observability only, no trading controls."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/monitoring">Monitoring</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/broker">Broker</Link>
            </Button>
          </div>
        }
      />

      <PageMotion className="space-y-4">
        <WeltradeGatewayStatus />
        <ExecutionStateStrip />
        <ExecutionMetricsStrip metrics={execMetrics} />
      </PageMotion>
    </div>
  );
}
