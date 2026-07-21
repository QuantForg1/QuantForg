"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Bot } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { DeskEmpty, DeskError, DeskSkeleton, DeskTable } from "@/components/desk/primitives";
import { iteOpsApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";

const AutoTradeControls = dynamic(
  () =>
    import("@/components/ops/auto-trade-controls").then((m) => m.AutoTradeControls),
  {
    ssr: false,
    loading: () => <DeskSkeleton rows={4} />,
  },
);

const LiveAutoTradeCertificationPanel = dynamic(
  () =>
    import("@/components/ops/live-auto-trade-certification").then(
      (m) => m.LiveAutoTradeCertificationPanel,
    ),
  {
    ssr: false,
    loading: () => <DeskSkeleton rows={4} />,
  },
);

export default function AutoTradingPage() {
  const auditQ = useQuery({
    queryKey: ["ite-ops-audit", 30],
    queryFn: () => iteOpsApi.audit(30),
    retry: false,
    refetchInterval: 30_000,
  });

  const rows = asList(auditQ.data?.items ?? auditQ.data)
    .map(asRecord)
    .slice(0, 30);

  return (
    <div>
      <PageHeader
        title="Auto Trading"
        description="Operator controls for automated execution. PME handles SL / TP / trail / BE / partial — never bypass risk."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/terminal">Terminal</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/ops">Ops</Link>
            </Button>
          </div>
        }
      />

      <PageMotion className="space-y-4">
        <p className="text-xs text-[var(--fg-muted)]">
          Position management (SL, TP, trailing, break-even, partials) runs through PME.
          Auto-trade never bypasses the risk engine or kill switch.
        </p>

        <AutoTradeControls />
        <LiveAutoTradeCertificationPanel />

        <Card>
          <CardHeader>
            <CardTitle>Auto Trade logs</CardTitle>
          </CardHeader>
          <CardContent>
            {auditQ.isLoading ? (
              <DeskSkeleton rows={6} />
            ) : auditQ.isError ? (
              <DeskError
                message="Unable to load auto-trade audit."
                onRetry={() => auditQ.refetch()}
              />
            ) : rows.length === 0 ? (
              <DeskEmpty
                icon={Bot}
                title="No auto-trade events"
                description="ITE ops audit entries for auto trading appear here when operators change controls."
              />
            ) : (
              <DeskTable
                columns={["Time", "Action", "Actor", "Detail"]}
                rows={rows.map((r) => [
                  str(r.created_at ?? r.timestamp ?? r.time),
                  str(r.action ?? r.event ?? r.type),
                  str(r.actor ?? r.user ?? r.operator),
                  str(r.detail ?? r.reason ?? r.message, "").slice(0, 120) || "—",
                ])}
              />
            )}
          </CardContent>
        </Card>
      </PageMotion>
    </div>
  );
}
