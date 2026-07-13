"use client";

import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { portfolioApi } from "@/lib/api/endpoints";

export default function Page() {
  const q = useQuery({
    queryKey: ["orders"],
    queryFn: portfolioApi.orders,
    retry: false,
  });

  return (
    <div>
      <PageHeader title="Orders" description="Pending and working orders from your connected portfolio." />
      <Card>
        <CardHeader>
          <CardTitle>Live API data</CardTitle>
        </CardHeader>
        <CardContent>
          {q.isLoading ? (
            <Skeleton className="h-40 w-full" />
          ) : q.isError ? (
            <p className="text-sm text-[var(--fg-muted)]">
              Unable to load this resource. Connect MT5 or ensure your session has access.
            </p>
          ) : (
            <pre className="max-h-[28rem] overflow-auto rounded-lg bg-[var(--bg-elevated)] p-4 text-xs text-[var(--fg-muted)]">
              {JSON.stringify(q.data, null, 2)}
            </pre>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
