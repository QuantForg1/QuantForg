"use client";

import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { walkforwardApi } from "@/lib/api/endpoints";

export default function WalkForwardPage() {
  const q = useQuery({
    queryKey: ["walkforward"],
    queryFn: walkforwardApi.list,
    retry: false,
  });

  return (
    <div>
      <PageHeader
        title="Walk Forward"
        description="Offline walk-forward validation results from the production API."
      />
      <Card>
        <CardHeader>
          <CardTitle>Results</CardTitle>
        </CardHeader>
        <CardContent>
          {q.isLoading ? (
            <Skeleton className="h-40 w-full" />
          ) : q.isError ? (
            <p className="text-sm text-[var(--fg-muted)]">
              Unable to load walk-forward results for this session.
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
