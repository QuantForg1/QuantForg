"use client";

import { memo, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  Bell,
  BookOpen,
  Cable,
  History,
  Layers3,
  ListOrdered,
  ListTodo,
  Radio,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { PositionManager } from "@/components/execution/position-manager";
import { OrdersWorkspace } from "@/components/execution/orders-workspace";
import { platformApi, portfolioApi, weltradeApi, executionApi } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { formatCurrency, formatRelativeTime } from "@/lib/utils";
import { useTradingSession } from "@/providers/trading-session-provider";
import type { WorkspaceLayoutState } from "@/components/workspace/layout-store";

type BottomTab = WorkspaceLayoutState["bottomTab"];

const TABS: { id: BottomTab; label: string; icon: typeof History }[] = [
  { id: "positions", label: "Open Positions", icon: Layers3 },
  { id: "orders", label: "Pending Orders", icon: ListOrdered },
  { id: "history", label: "Trade History", icon: History },
  { id: "journal", label: "Journal", icon: BookOpen },
  { id: "execution", label: "Execution Log", icon: ListTodo },
  { id: "gateway", label: "Gateway Log", icon: Radio },
  { id: "broker", label: "Broker Log", icon: Cable },
  { id: "system", label: "System Log", icon: Activity },
  { id: "notifications", label: "Notifications", icon: Bell },
];

export const WorkspaceBottomPanel = memo(function WorkspaceBottomPanel({
  tab,
  onTabChange,
}: {
  tab: BottomTab;
  onTabChange: (t: BottomTab) => void;
}) {
  const session = useTradingSession();
  const historyQ = useQuery({
    queryKey: ["history"],
    queryFn: portfolioApi.history,
    retry: false,
    enabled: tab === "history",
    staleTime: 20_000,
  });
  const activityQ = useQuery({
    queryKey: ["activity"],
    queryFn: platformApi.activity,
    retry: false,
    enabled: tab === "system" || tab === "broker",
  });
  const notifQ = useQuery({
    queryKey: ["notifications"],
    queryFn: () => platformApi.notifications(false),
    retry: false,
    enabled: tab === "notifications",
  });
  const healthQ = useQuery({
    queryKey: ["weltrade-health"],
    queryFn: weltradeApi.health,
    retry: false,
    enabled: tab === "gateway" || tab === "broker",
    staleTime: 15_000,
  });

  const journalQ = useQuery({
    queryKey: ["execution-journal"],
    queryFn: () => executionApi.journal(100),
    retry: false,
    enabled: tab === "journal" || tab === "execution",
    staleTime: 8_000,
    refetchInterval: tab === "journal" || tab === "execution" ? 12_000 : false,
  });
  const analyticsQ = useQuery({
    queryKey: ["execution-analytics"],
    queryFn: () => executionApi.analytics(200),
    retry: false,
    enabled: tab === "execution",
    staleTime: 15_000,
  });

  const deals = useMemo(() => {
    const fromApi = asList(historyQ.data?.deals).map(asRecord);
    return fromApi.length ? fromApi : session.historyDeals;
  }, [historyQ.data, session.historyDeals]);
  const histOrders = useMemo(
    () => asList(historyQ.data?.orders).map(asRecord),
    [historyQ.data],
  );
  const journalRows = useMemo(
    () => asList(asRecord(journalQ.data).items).map(asRecord),
    [journalQ.data],
  );
  const analytics = asRecord(analyticsQ.data);
  const analyticsMetrics = asRecord(analytics.metrics);
  const activity = useMemo(() => asList(activityQ.data).map(asRecord), [activityQ.data]);
  const notifications = useMemo(() => asList(notifQ.data).map(asRecord), [notifQ.data]);
  const health = asRecord(healthQ.data);

  return (
    <section
      className="flex h-full min-h-0 flex-col bg-[var(--bg-elevated)]/50"
      aria-label="Institutional book panel"
    >
      <div
        className="flex flex-wrap items-center gap-1 border-b border-[var(--border)] px-2 py-1.5"
        role="tablist"
        aria-label="Bottom panels"
      >
        {TABS.map((t) => {
          const Icon = t.icon;
          return (
            <Button
              key={t.id}
              size="sm"
              role="tab"
              aria-selected={tab === t.id}
              variant={tab === t.id ? "default" : "ghost"}
              className="h-7 gap-1.5 px-2 text-[11px]"
              onClick={() => onTabChange(t.id)}
            >
              <Icon className="h-3.5 w-3.5" />
              {t.label}
            </Button>
          );
        })}
      </div>

      <div className="min-h-0 flex-1 overflow-auto" role="tabpanel">
        {tab === "positions" ? (
          <div className="p-2">
            <PositionManager connected={session.connected} />
          </div>
        ) : tab === "orders" ? (
          <div className="p-2">
            <OrdersWorkspace connected={session.connected} />
          </div>
        ) : tab === "history" ? (
          historyQ.isLoading && !deals.length ? (
            <div className="p-3">
              <DeskSkeleton rows={4} />
            </div>
          ) : historyQ.isError && !deals.length ? (
            <div className="p-3">
              <DeskError
                message="Unable to load trade history."
                onRetry={() => historyQ.refetch()}
              />
            </div>
          ) : deals.length === 0 ? (
            <DeskEmpty
              icon={History}
              title="No completed trades"
              description="Synced MT5 deals appear here."
            />
          ) : (
            <table className="w-full text-left text-[11px]" aria-label="Trade history">
              <thead className="sticky top-0 bg-[var(--surface-2)] text-[var(--fg-subtle)]">
                <tr>
                  <th className="px-2 py-1.5 font-medium">Symbol</th>
                  <th className="px-2 py-1.5 font-medium">Side</th>
                  <th className="px-2 py-1.5 font-medium">Volume</th>
                  <th className="px-2 py-1.5 font-medium">Profit</th>
                  <th className="px-2 py-1.5 font-medium">Time</th>
                </tr>
              </thead>
              <tbody>
                {deals.slice(0, 80).map((d, i) => (
                  <tr key={`${str(d.ticket)}-${i}`} className="border-t border-[var(--border)]">
                    <td className="px-2 py-1.5 font-medium">{str(d.symbol)}</td>
                    <td className="px-2 py-1.5">{str(d.side || d.deal_type)}</td>
                    <td className="tabular px-2 py-1.5">{str(d.volume)}</td>
                    <td
                      className={`tabular px-2 py-1.5 ${
                        num(d.profit, 0) >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]"
                      }`}
                    >
                      {Number.isFinite(num(d.profit))
                        ? formatCurrency(num(d.profit))
                        : str(d.profit)}
                    </td>
                    <td className="px-2 py-1.5 text-[var(--fg-subtle)]">
                      {str(d.time, "—").replace("T", " ").slice(0, 19)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        ) : tab === "journal" ? (
          journalQ.isLoading && !journalRows.length ? (
            <div className="p-3">
              <DeskSkeleton rows={4} />
            </div>
          ) : journalRows.length === 0 ? (
            <DeskEmpty
              icon={BookOpen}
              title="No execution journal yet"
              description="Pipeline runs (submit / cancel / OMS) appear here with latency and result."
            />
          ) : (
            <table className="w-full text-left text-[11px]" aria-label="Execution journal">
              <thead className="sticky top-0 bg-[var(--surface-2)] text-[var(--fg-subtle)]">
                <tr>
                  <th className="px-2 py-1.5 font-medium">Time</th>
                  <th className="px-2 py-1.5 font-medium">Action</th>
                  <th className="px-2 py-1.5 font-medium">Symbol</th>
                  <th className="px-2 py-1.5 font-medium">Ticket</th>
                  <th className="px-2 py-1.5 font-medium">Latency</th>
                  <th className="px-2 py-1.5 font-medium">Result</th>
                  <th className="px-2 py-1.5 font-medium">Reason</th>
                </tr>
              </thead>
              <tbody>
                {journalRows.slice(0, 80).map((j, i) => (
                  <tr key={`${str(j.journal_id)}-${i}`} className="border-t border-[var(--border)]">
                    <td className="px-2 py-1.5 text-[var(--fg-subtle)]">
                      {str(j.timestamp, "—").replace("T", " ").slice(0, 19)}
                    </td>
                    <td className="px-2 py-1.5">{str(j.action)}</td>
                    <td className="px-2 py-1.5 font-medium">{str(j.symbol)}</td>
                    <td className="tabular px-2 py-1.5">{str(j.ticket, "—")}</td>
                    <td className="tabular px-2 py-1.5">
                      {j.latency_ms != null ? `${Number(j.latency_ms).toFixed(1)} ms` : "—"}
                    </td>
                    <td className="px-2 py-1.5">{str(j.execution_result)}</td>
                    <td className="max-w-[14rem] truncate px-2 py-1.5 text-[var(--fg-subtle)]">
                      {str(j.reason)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        ) : tab === "execution" ? (
          <div className="space-y-3 p-2">
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 text-[11px]">
              {(
                [
                  ["Fill rate", analyticsMetrics.fill_rate],
                  ["Success rate", analyticsMetrics.success_rate],
                  ["Avg latency", analyticsMetrics.latency_ms_avg],
                  ["Rejected", analyticsMetrics.rejected_orders],
                ] as const
              ).map(([label, value]) => (
                <div key={label} className="rounded border border-[var(--border)] px-2 py-1.5">
                  <p className="text-[var(--fg-subtle)]">{label}</p>
                  <p className="tabular font-medium">
                    {value == null || value === ""
                      ? "—"
                      : typeof value === "number" && label.includes("rate")
                        ? `${(Number(value) * 100).toFixed(1)}%`
                        : String(value)}
                  </p>
                </div>
              ))}
            </div>
            {journalRows.length === 0 && histOrders.length === 0 && deals.length === 0 ? (
              <DeskEmpty
                icon={ListTodo}
                title="No execution tape"
                description="Institutional pipeline stages and broker outcomes appear here."
              />
            ) : (
              <table className="w-full text-left text-[11px]" aria-label="Execution log">
                <thead className="sticky top-0 bg-[var(--surface-2)] text-[var(--fg-subtle)]">
                  <tr>
                    <th className="px-2 py-1.5 font-medium">Request</th>
                    <th className="px-2 py-1.5 font-medium">Symbol</th>
                    <th className="px-2 py-1.5 font-medium">Stages</th>
                    <th className="px-2 py-1.5 font-medium">Result</th>
                    <th className="px-2 py-1.5 font-medium">Slippage</th>
                  </tr>
                </thead>
                <tbody>
                  {(journalRows.length
                    ? journalRows
                    : histOrders.length
                      ? histOrders
                      : deals
                  )
                    .slice(0, 60)
                    .map((row, i) => (
                      <tr
                        key={`${str(row.journal_id || row.ticket)}-e-${i}`}
                        className="border-t border-[var(--border)]"
                      >
                        <td className="truncate px-2 py-1.5 font-mono text-[10px]">
                          {str(row.request_id || row.ticket)}
                        </td>
                        <td className="px-2 py-1.5">{str(row.symbol)}</td>
                        <td className="tabular px-2 py-1.5">
                          {asList(row.stages).length || str(row.order_type || row.side)}
                        </td>
                        <td className="px-2 py-1.5">
                          {str(row.execution_result || row.state || row.deal_type, "—")}
                        </td>
                        <td className="tabular px-2 py-1.5">{str(row.slippage, "—")}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            )}
          </div>
        ) : tab === "gateway" ? (
          <div className="space-y-2 p-3 text-[11px]">
            <div className="flex items-center gap-2">
              <Badge tone={session.gatewayOnline ? "success" : "warning"}>
                {session.gatewayLabel}
              </Badge>
              <span className="text-[var(--fg-subtle)]">
                Latency {session.latencyMs !== "—" ? `${session.latencyMs} ms` : "—"}
              </span>
            </div>
            <dl className="grid grid-cols-2 gap-2">
              <div>
                <dt className="text-[var(--fg-subtle)]">URL</dt>
                <dd className="truncate font-mono">{session.gatewayUrl || "—"}</dd>
              </div>
              <div>
                <dt className="text-[var(--fg-subtle)]">HTTP</dt>
                <dd className="font-mono">{str(health.last_http_status, "—")}</dd>
              </div>
              <div>
                <dt className="text-[var(--fg-subtle)]">Redirects</dt>
                <dd className="font-mono">{str(health.redirects_followed, "—")}</dd>
              </div>
              <div>
                <dt className="text-[var(--fg-subtle)]">Detail</dt>
                <dd className="break-words font-mono">{session.gatewayDetail || "ok"}</dd>
              </div>
            </dl>
          </div>
        ) : tab === "broker" ? (
          <div className="space-y-2 p-3 text-[11px]">
            <div className="flex flex-wrap gap-2">
              <Badge tone={session.connected ? "success" : "warning"}>
                {session.connected ? "Session attached" : "Detached"}
              </Badge>
              <Badge tone={session.brokerConnected ? "accent" : "neutral"}>
                Broker {session.brokerConnected ? "online" : "idle"}
              </Badge>
            </div>
            <dl className="grid grid-cols-2 gap-2">
              <div>
                <dt className="text-[var(--fg-subtle)]">Login</dt>
                <dd className="font-mono">{session.login}</dd>
              </div>
              <div>
                <dt className="text-[var(--fg-subtle)]">Server</dt>
                <dd className="font-mono">{session.server}</dd>
              </div>
              <div>
                <dt className="text-[var(--fg-subtle)]">Login status</dt>
                <dd className="font-mono">{session.loginStatus}</dd>
              </div>
              <div>
                <dt className="text-[var(--fg-subtle)]">Heartbeat</dt>
                <dd className="font-mono">
                  {session.heartbeatAt.replace("T", " ").slice(0, 19) || "—"}
                </dd>
              </div>
            </dl>
            {activity.length ? (
              <ul className="mt-2 space-y-1 border-t border-[var(--border)] pt-2">
                {activity.slice(0, 12).map((a, i) => (
                  <li key={i} className="text-[var(--fg-muted)]">
                    {str(a.message || a.event || a.action)} ·{" "}
                    {formatRelativeTime(str(a.created_at || a.time))}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : tab === "system" ? (
          activityQ.isLoading ? (
            <div className="p-3">
              <DeskSkeleton rows={4} />
            </div>
          ) : activity.length === 0 ? (
            <DeskEmpty
              icon={Activity}
              title="No system events"
              description="Platform activity stream is empty."
            />
          ) : (
            <ul className="divide-y divide-[var(--border)] text-[11px]">
              {activity.slice(0, 40).map((a, i) => (
                <li key={i} className="px-3 py-2">
                  <p className="text-[var(--fg)]">{str(a.message || a.event || a.action)}</p>
                  <p className="text-[var(--fg-subtle)]">
                    {formatRelativeTime(str(a.created_at || a.time))}
                  </p>
                </li>
              ))}
            </ul>
          )
        ) : notifQ.isLoading ? (
          <div className="p-3">
            <DeskSkeleton rows={4} />
          </div>
        ) : notifications.length === 0 ? (
          <DeskEmpty
            icon={Bell}
            title="No notifications"
            description="Desk alerts appear here when raised."
          />
        ) : (
          <ul className="divide-y divide-[var(--border)] text-[11px]">
            {notifications.slice(0, 40).map((n, i) => (
              <li key={i} className="px-3 py-2">
                <p className="font-medium text-[var(--fg)]">{str(n.title || n.message)}</p>
                <p className="text-[var(--fg-subtle)]">
                  {formatRelativeTime(str(n.created_at || n.time))}
                </p>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
});
