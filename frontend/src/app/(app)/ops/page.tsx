"use client";

import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { opsApi, platformApi } from "@/lib/api/endpoints";

export default function OpsPage() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: platformApi.health,
    retry: false,
  });
  const dashboard = useQuery({
    queryKey: ["ops-dashboard"],
    queryFn: opsApi.dashboard,
    retry: false,
  });

  return (
    <div>
      <PageHeader
        title="Operations"
        description="Health, metrics, and ops dashboard (owner/admin for privileged views)."
      />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>API health</CardTitle>
            <Badge
              tone={
                health.data?.status === "healthy"
                  ? "success"
                  : health.data?.status === "alive"
                    ? "accent"
                    : "warning"
              }
            >
              {String(health.data?.status ?? (health.isError ? "error" : "…"))}
            </Badge>
          </CardHeader>
          <CardContent>
            {health.isLoading ? (
              <Skeleton className="h-32 w-full" />
            ) : (
              <pre className="max-h-80 overflow-auto rounded-lg bg-[var(--bg-elevated)] p-4 text-xs text-[var(--fg-muted)]">
                {JSON.stringify(health.data ?? health.error, null, 2)}
              </pre>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Ops dashboard</CardTitle>
          </CardHeader>
          <CardContent>
            {dashboard.isLoading ? (
              <Skeleton className="h-32 w-full" />
            ) : dashboard.isError ? (
              <p className="text-sm text-[var(--fg-muted)]">
                Ops dashboard requires owner/admin. Non-admin sessions receive 401/403 by
                design.
              </p>
            ) : (
              <pre className="max-h-80 overflow-auto rounded-lg bg-[var(--bg-elevated)] p-4 text-xs text-[var(--fg-muted)]">
                {JSON.stringify(dashboard.data, null, 2)}
              </pre>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
