"use client";

import Link from "next/link";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { PageHeader } from "@/components/layout/page-header";
import { StatCard } from "@/components/dashboard/stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskError, DeskSkeleton, DeskTable } from "@/components/desk/primitives";
import { brokerConnectivityApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, str } from "@/lib/desk";

function toneFor(status: string): "success" | "warning" | "danger" | "neutral" {
  const s = status.toLowerCase();
  if (s.includes("certified") || s === "healthy") return "success";
  if (s.includes("pending") || s.includes("not tested") || s === "degraded")
    return "warning";
  if (s.includes("failed")) return "danger";
  return "neutral";
}

export default function BrokerCertificationPage() {
  const dashQ = useQuery({
    queryKey: ["broker-certification-dashboard"],
    queryFn: brokerConnectivityApi.certificationDashboard,
    retry: false,
  });

  const run = useMutation({
    mutationFn: () => brokerConnectivityApi.runCertification({ tester: "operator" }),
    onSuccess: async () => {
      toast.success("Certification run recorded");
      await dashQ.refetch();
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Certification run failed"),
  });

  const data = asRecord(dashQ.data);
  const certified = asList(data.certified_brokers).map(asRecord);
  const pending = asList(data.pending_brokers).map(asRecord);
  const failed = asList(data.failed_certifications).map(asRecord);
  const brokers = asList(data.brokers).map(asRecord);
  const history = asList(data.history).map(asRecord);
  const lastTest = asRecord(data.last_test);
  const health = asList(data.health_status).map(asRecord);

  return (
    <div>
      <PageHeader
        title="Broker Certification"
        description="Advance Pending Session → Certified using real MT5 sessions only."
        actions={
          <div className="flex gap-2">
            <Button size="sm" variant="secondary" asChild>
              <Link href="/mt5">Connect MT5</Link>
            </Button>
            <Button
              size="sm"
              disabled={run.isPending}
              onClick={() => run.mutate()}
            >
              Run certification
            </Button>
            <Button size="sm" variant="secondary" onClick={() => dashQ.refetch()}>
              Refresh
            </Button>
          </div>
        }
      />

      {dashQ.isLoading ? (
        <DeskSkeleton rows={6} />
      ) : dashQ.isError ? (
        <DeskError
          message="Certification dashboard unavailable."
          onRetry={() => dashQ.refetch()}
        />
      ) : (
        <div className="space-y-4">
          <p className="text-xs text-[var(--fg-subtle)]">{str(data.notes)}</p>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Certified" value={String(certified.length)} />
            <StatCard label="Pending" value={String(pending.length)} />
            <StatCard label="Failed" value={String(failed.length)} />
            <StatCard
              label="Last test"
              value={str(lastTest.name) || "n/a"}
              hint={str(lastTest.last_test_at) || undefined}
            />
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Certification status</CardTitle>
            </CardHeader>
            <CardContent>
              <DeskTable
                columns={[
                  "Broker",
                  "State",
                  "Health",
                  "Server",
                  "Currency",
                  "Leverage",
                  "Symbols",
                  "Quote ms",
                  "Heartbeat",
                  "Last cert",
                ]}
                rows={brokers.map((b) => {
                  const report = asRecord(b.report);
                  return [
                    str(b.name),
                    <Badge key="s" tone={toneFor(str(b.state))}>
                      {str(b.state)}
                    </Badge>,
                    <Badge key="h" tone={toneFor(str(b.health_status))}>
                      {str(b.health_status)}
                    </Badge>,
                    str(report.server_name) || "—",
                    str(report.account_currency) || "—",
                    report.leverage == null ? "—" : String(report.leverage),
                    report.symbols_available == null
                      ? "—"
                      : String(report.symbols_available),
                    report.quote_latency_ms == null
                      ? "—"
                      : String(report.quote_latency_ms),
                    str(report.heartbeat_stability) || "—",
                    str(b.last_certification_time) || "—",
                  ];
                })}
              />
            </CardContent>
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Health status</CardTitle>
              </CardHeader>
              <CardContent>
                <DeskTable
                  columns={["Broker", "Health", "State"]}
                  rows={health.map((h) => [
                    str(h.name),
                    <Badge key="h" tone={toneFor(str(h.health_status))}>
                      {str(h.health_status)}
                    </Badge>,
                    str(h.state),
                  ])}
                />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Certification history</CardTitle>
              </CardHeader>
              <CardContent>
                {history.length === 0 ? (
                  <p className="text-sm text-[var(--fg-subtle)]">
                    No runs yet — connect MT5 and run certification.
                  </p>
                ) : (
                  <DeskTable
                    columns={["Date", "Broker", "Result", "Failure", "Tester"]}
                    rows={history.slice(0, 20).map((h) => [
                      str(h.date),
                      str(h.broker_name) || str(h.broker),
                      <Badge key="r" tone={toneFor(str(h.result))}>
                        {str(h.result)}
                      </Badge>,
                      str(h.failure_reason) || "—",
                      str(h.tester) || "—",
                    ])}
                  />
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
