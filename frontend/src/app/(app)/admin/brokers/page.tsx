"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { Building2, RefreshCw } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  DeskEmpty,
  DeskError,
  DeskSkeleton,
  DeskTable,
} from "@/components/desk/primitives";
import { NocPanel } from "@/components/ops/noc/noc-primitives";
import { customerOpsApi } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { useAuth } from "@/providers/auth-provider";
import {
  canAccessIteOps,
  iteOpsAccessDeniedMessage,
} from "@/lib/auth/ite-ops-access";

function fmt(v: unknown, fallback = "—"): string {
  if (v === null || v === undefined || v === "") return fallback;
  return String(v);
}

function healthTone(
  health: string,
): "success" | "warning" | "danger" | "neutral" {
  const h = health.toLowerCase();
  if (h === "healthy" || h === "connected" || h === "ok") return "success";
  if (h === "unknown" || h === "") return "neutral";
  if (h.includes("degrad") || h.includes("latency")) return "warning";
  return "danger";
}

export default function AdminBrokersPage() {
  const { user, opsReady, isAuthenticated } = useAuth();
  const allowed = canAccessIteOps(user);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const brokersQ = useQuery({
    queryKey: ["admin-brokers-center"],
    queryFn: () => customerOpsApi.brokers(),
    enabled: allowed && opsReady && isAuthenticated,
    retry: 1,
    staleTime: 20_000,
  });

  const fleetQ = useQuery({
    queryKey: ["admin-brokers-fleet"],
    queryFn: () => customerOpsApi.fleet(),
    enabled: allowed && opsReady && isAuthenticated,
    retry: false,
    staleTime: 60_000,
  });

  const emailByUserId = useMemo(() => {
    const map = new Map<string, string>();
    const fleet = asRecord(fleetQ.data);
    for (const row of asList(fleet.customers)) {
      const r = asRecord(row);
      const id = str(r.id ?? r.customer_id ?? r.user_id, "");
      const email = str(r.email, "");
      if (id && email) map.set(id, email);
    }
    return map;
  }, [fleetQ.data]);

  if (!allowed) {
    return (
      <DeskError
        message={iteOpsAccessDeniedMessage(user, undefined, "Broker Management")}
      />
    );
  }

  if (!opsReady || brokersQ.isLoading || brokersQ.isPending) {
    return <DeskSkeleton variant="page" />;
  }

  if (brokersQ.isError && !brokersQ.data) {
    return (
      <DeskError
        message={iteOpsAccessDeniedMessage(
          user,
          brokersQ.error,
          "Broker Management",
        )}
        onRetry={() => void brokersQ.refetch()}
      />
    );
  }

  const data = asRecord(brokersQ.data);
  const connections = asList(data.connections);
  const history = asList(data.connection_history);
  const connected = num(data.connected, NaN);
  const total = num(data.count, connections.length);

  const selected =
    connections.find((row) => {
      const r = asRecord(row);
      return str(r.id, "") === selectedId;
    }) ?? null;
  const selectedRec = selected ? asRecord(selected) : null;

  return (
    <div className="min-w-0 space-y-4">
      <PageHeader
        eyebrow="Broker Management"
        title="Connected brokers"
        description="Ownership and connection health from production MT5 bindings. Credentials and tokens are never returned. Disconnect and ownership transfer are not available from this surface."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={brokersQ.isFetching}
              onClick={() => void brokersQ.refetch()}
            >
              <RefreshCw className="mr-1.5 h-3.5 w-3.5" aria-hidden />
              Refresh
            </Button>
            <Button asChild size="sm" variant="secondary">
              <Link href="/admin/customer-ops#brokers">COP brokers</Link>
            </Button>
          </div>
        }
      />

      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="neutral">As of {fmt(data.as_of)}</Badge>
        <Badge tone="success">
          credentials exposed · {fmt(data.credentials_exposed, "false")}
        </Badge>
        <Badge tone="neutral">
          {Number.isFinite(connected) ? `${connected} connected` : "—"} ·{" "}
          {total} total
        </Badge>
        {data.fabricated === true ? (
          <Badge tone="warning">Synthetic payload</Badge>
        ) : null}
      </div>

      {connections.length === 0 ? (
        <DeskEmpty
          icon={Building2}
          title="No broker connections"
          description="Production MT5 connection rows will appear here when customers link accounts."
        />
      ) : (
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(20rem,0.8fr)]">
          <NocPanel title="Broker inventory">
            <DeskTable
              columns={[
                "Broker",
                "Owner",
                "Account",
                "Server",
                "Health",
                "Latency",
                "Last sync",
              ]}
              rows={connections.map((row) => {
                const r = asRecord(row);
                const id = str(r.id, "");
                const uid = str(r.user_id, "");
                const owner = emailByUserId.get(uid) || uid || "—";
                const health = str(r.connection_health, "unknown");
                return [
                  <button
                    key={`${id}-broker`}
                    type="button"
                    className="text-left font-medium text-[var(--fg)] hover:text-[var(--accent)]"
                    onClick={() => setSelectedId(id || null)}
                  >
                    {fmt(r.broker, "MT5")}
                  </button>,
                  uid ? (
                    <Link
                      key={`${id}-owner`}
                      href={`/admin/users/${encodeURIComponent(uid)}`}
                      className="text-[var(--accent)] hover:underline"
                    >
                      {owner}
                    </Link>
                  ) : (
                    owner
                  ),
                  <span key={`${id}-login`} className="font-mono text-[12px]">
                    {fmt(r.login)}
                  </span>,
                  fmt(r.server),
                  <Badge key={`${id}-health`} tone={healthTone(health)}>
                    {health}
                  </Badge>,
                  fmt(r.latency_ms),
                  fmt(r.last_heartbeat).slice(0, 19),
                ];
              })}
            />
          </NocPanel>

          <div className="space-y-4">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Connection detail</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-[12px] text-[var(--fg-muted)]">
                {!selectedRec ? (
                  <p>Select a broker row to inspect ownership and health.</p>
                ) : (
                  <>
                    <p>
                      <span className="text-[var(--fg-subtle)]">Broker · </span>
                      {fmt(selectedRec.broker, "MT5")}
                    </p>
                    <p>
                      <span className="text-[var(--fg-subtle)]">Server · </span>
                      {fmt(selectedRec.server)}
                    </p>
                    <p>
                      <span className="text-[var(--fg-subtle)]">Account · </span>
                      <span className="font-mono">{fmt(selectedRec.login)}</span>
                    </p>
                    <p>
                      <span className="text-[var(--fg-subtle)]">Owner · </span>
                      {selectedRec.user_id ? (
                        <Link
                          href={`/admin/users/${encodeURIComponent(String(selectedRec.user_id))}`}
                          className="text-[var(--accent)] hover:underline"
                        >
                          {emailByUserId.get(String(selectedRec.user_id)) ||
                            String(selectedRec.user_id)}
                        </Link>
                      ) : (
                        "—"
                      )}
                    </p>
                    <p>
                      <span className="text-[var(--fg-subtle)]">Health · </span>
                      {fmt(selectedRec.connection_health)}
                    </p>
                    <p>
                      <span className="text-[var(--fg-subtle)]">
                        Last sync ·{" "}
                      </span>
                      {fmt(selectedRec.last_heartbeat)}
                    </p>
                    <p>
                      <span className="text-[var(--fg-subtle)]">
                        Trading permission ·{" "}
                      </span>
                      {fmt(selectedRec.trading_permission)}
                    </p>
                    <p>
                      <span className="text-[var(--fg-subtle)]">
                        Auto-trading ·{" "}
                      </span>
                      {fmt(selectedRec.auto_trading_status)}
                    </p>
                    <p>
                      <span className="text-[var(--fg-subtle)]">
                        Last error ·{" "}
                      </span>
                      {fmt(selectedRec.last_error)}
                    </p>
                    <p className="pt-2 text-[11px] text-[var(--fg-subtle)]">
                      Revoke/disconnect and ownership transfer are not exposed
                      on this admin surface. Use the customer&apos;s own broker
                      settings or authorized support workflows.
                    </p>
                  </>
                )}
              </CardContent>
            </Card>

            <NocPanel title="Connection history">
              {history.length === 0 ? (
                <p className="text-[12px] text-[var(--fg-muted)]">
                  No COP broker history events recorded yet.
                </p>
              ) : (
                <ul className="max-h-64 space-y-1 overflow-y-auto text-[12px]">
                  {history.slice(0, 40).map((row, i) => {
                    const r = asRecord(row);
                    return (
                      <li
                        key={str(r.id ?? r.at, `hist-${i}`)}
                        className="flex justify-between gap-2 border-b border-[var(--border)] py-1.5 last:border-0"
                      >
                        <span className="truncate">
                          {fmt(r.action ?? r.event ?? r.note ?? r.type)}
                        </span>
                        <span className="shrink-0 text-[var(--fg-muted)]">
                          {fmt(r.at ?? r.created_at).slice(0, 19)}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              )}
            </NocPanel>
          </div>
        </div>
      )}
    </div>
  );
}
