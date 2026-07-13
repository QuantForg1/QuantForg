"use client";

import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { paperApi } from "@/lib/api/endpoints";

export default function Page() {
  const q = useQuery({
    queryKey: ["paper"],
    queryFn: paperApi.performance,
    retry: false,
  });

  return (
    <div>
      <PageHeader title="Paper Trading" description="Simulate fills without touching live execution." />
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
