"use client";

import { memo, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { platformApi, portfolioApi } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { formatCurrency, formatRelativeTime } from "@/lib/utils";
import type { WorkspaceLayoutState } from "@/components/workspace/layout-store";
import { History, ListTodo, Activity as ActivityIcon, Bell as BellIcon } from "lucide-react";

type BottomTab = WorkspaceLayoutState["bottomTab"];

const TABS: { id: BottomTab; label: string; icon: typeof History }[] = [
  { id: "history", label: "Trade History", icon: History },
  { id: "execution", label: "Execution Log", icon: ListTodo },
  { id: "system", label: "System Log", icon: ActivityIcon },
  { id: "notifications", label: "Notifications", icon: BellIcon },
];

export const WorkspaceBottomPanel = memo(function WorkspaceBottomPanel({
  tab,
  onTabChange,
}: {
  tab: BottomTab;
  onTabChange: (t: BottomTab) => void;
}) {
  const historyQ = useQuery({
    queryKey: ["history"],
    queryFn: portfolioApi.history,
    retry: false,
    enabled: tab === "history" || tab === "execution",
  });
  const activityQ = useQuery({
    queryKey: ["activity"],
    queryFn: platformApi.activity,
    retry: false,
    enabled: tab === "system",
  });
  const notifQ = useQuery({
    queryKey: ["notifications"],
    queryFn: () => platformApi.notifications(false),
    retry: false,
    enabled: tab === "notifications",
  });

  const deals = useMemo(() => asList(historyQ.data?.deals).map(asRecord), [historyQ.data]);
  const histOrders = useMemo(
    () => asList(historyQ.data?.orders).map(asRecord),
    [historyQ.data],
  );
  const activity = useMemo(() => asList(activityQ.data).map(asRecord), [activityQ.data]);
  const notifications = useMemo(() => asList(notifQ.data).map(asRecord), [notifQ.data]);

  return (
    <section className="flex h-full min-h-0 flex-col bg-[var(--bg-elevated)]/50" aria-label="Bottom workspace panel">
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
        {tab === "history" ? (
          historyQ.isLoading ? (
            <div className="p-3">
              <DeskSkeleton rows={4} />
            </div>
          ) : historyQ.isError ? (
            <div className="p-3">
              <DeskError message="Unable to load trade history." onRetry={() => historyQ.refetch()} />
            </div>
          ) : deals.length === 0 ? (
            <DeskEmpty
              icon={History}
              title="No deals yet"
              description="Synced MT5 deals appear here."
            />
          ) : (
            <table className="w-full text-left text-[11px]" aria-label="Trade history">
              <thead className="sticky top-0 bg-[var(--surface-2)] text-[var(--fg-subtle)]">
                <tr>
                  <th className="px-3 py-2 font-medium">Time</th>
                  <th className="px-3 py-2 font-medium">Symbol</th>
                  <th className="px-3 py-2 font-medium">Side</th>
                  <th className="px-3 py-2 font-medium">Volume</th>
                  <th className="px-3 py-2 font-medium">Price</th>
                  <th className="px-3 py-2 font-medium">PnL</th>
                </tr>
              </thead>
              <tbody>
                {deals.slice(0, 200).map((d, i) => {
                  const pnl = num(d.profit, 0);
                  return (
                    <tr
                      key={str(d.ticket, str(d.deal, String(i)))}
                      className="border-t border-[var(--border)]"
                    >
                      <td className="px-3 py-1.5 text-[var(--fg-muted)]">
                        {formatRelativeTime(str(d.time))}
                      </td>
                      <td className="px-3 py-1.5 font-medium">{str(d.symbol)}</td>
                      <td className="px-3 py-1.5">{str(d.side, str(d.type))}</td>
                      <td className="px-3 py-1.5 tabular">{str(d.volume)}</td>
                      <td className="px-3 py-1.5 tabular">{str(d.price)}</td>
                      <td
                        className={`px-3 py-1.5 tabular ${
                          pnl >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]"
                        }`}
                      >
                        {formatCurrency(pnl)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )
        ) : null}

        {tab === "execution" ? (
          historyQ.isLoading ? (
            <div className="p-3">
              <DeskSkeleton rows={4} />
            </div>
          ) : historyQ.isError ? (
            <div className="p-3">
              <DeskError
                message="Unable to load execution history."
                onRetry={() => historyQ.refetch()}
              />
            </div>
          ) : histOrders.length === 0 ? (
            <DeskEmpty
              icon={ListTodo}
              title="No execution records"
              description="Historical orders from the terminal sync populate this log."
            />
          ) : (
            <table className="w-full text-left text-[11px]" aria-label="Execution log">
              <thead className="sticky top-0 bg-[var(--surface-2)] text-[var(--fg-subtle)]">
                <tr>
                  <th className="px-3 py-2 font-medium">Time</th>
                  <th className="px-3 py-2 font-medium">Ticket</th>
                  <th className="px-3 py-2 font-medium">Symbol</th>
                  <th className="px-3 py-2 font-medium">Type</th>
                  <th className="px-3 py-2 font-medium">State</th>
                  <th className="px-3 py-2 font-medium">Volume</th>
                </tr>
              </thead>
              <tbody>
                {histOrders.slice(0, 200).map((o, i) => (
                  <tr
                    key={str(o.ticket, String(i))}
                    className="border-t border-[var(--border)]"
                  >
                    <td className="px-3 py-1.5 text-[var(--fg-muted)]">
                      {formatRelativeTime(str(o.time_setup ?? o.time ?? o.created_at))}
                    </td>
                    <td className="px-3 py-1.5 tabular">{str(o.ticket)}</td>
                    <td className="px-3 py-1.5 font-medium">{str(o.symbol)}</td>
                    <td className="px-3 py-1.5">{str(o.order_type, str(o.type))}</td>
                    <td className="px-3 py-1.5">
                      <Badge tone="neutral" className="text-[10px]">
                        {str(o.state, str(o.status, "—"))}
                      </Badge>
                    </td>
                    <td className="px-3 py-1.5 tabular">{str(o.volume)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        ) : null}

        {tab === "system" ? (
          activityQ.isLoading ? (
            <div className="p-3">
              <DeskSkeleton rows={4} />
            </div>
          ) : activityQ.isError ? (
            <div className="p-3">
              <DeskError message="Unable to load activity." onRetry={() => activityQ.refetch()} />
            </div>
          ) : activity.length === 0 ? (
            <DeskEmpty
              icon={ActivityIcon}
              title="No system activity"
              description="Profile activity events appear here."
            />
          ) : (
            <ul className="divide-y divide-[var(--border)]" aria-label="System log">
              {activity.slice(0, 100).map((a, i) => (
                <li key={str(a.id, String(i))} className="px-3 py-2 text-[11px]">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium text-[var(--fg)]">
                      {str(a.action, str(a.event, str(a.type, "Activity")))}
                    </span>
                    <span className="text-[var(--fg-subtle)]">
                      {formatRelativeTime(str(a.created_at, str(a.time)))}
                    </span>
                  </div>
                  <p className="mt-0.5 text-[var(--fg-muted)]">
                    {str(a.description, str(a.message, str(a.details, "—")))}
                  </p>
                </li>
              ))}
            </ul>
          )
        ) : null}

        {tab === "notifications" ? (
          notifQ.isLoading ? (
            <div className="p-3">
              <DeskSkeleton rows={4} />
            </div>
          ) : notifQ.isError ? (
            <div className="p-3">
              <DeskError
                message="Unable to load notifications."
                onRetry={() => notifQ.refetch()}
              />
            </div>
          ) : notifications.length === 0 ? (
            <DeskEmpty
              icon={BellIcon}
              title="Inbox clear"
              description="No notifications from the platform API."
            />
          ) : (
            <ul className="divide-y divide-[var(--border)]" aria-label="Notifications">
              {notifications.slice(0, 100).map((n, i) => (
                <li key={str(n.id, String(i))} className="px-3 py-2 text-[11px]">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium">{str(n.title)}</span>
                    <span className="text-[var(--fg-subtle)]">
                      {formatRelativeTime(str(n.created_at))}
                    </span>
                  </div>
                  <p className="mt-0.5 text-[var(--fg-muted)]">{str(n.body)}</p>
                </li>
              ))}
            </ul>
          )
        ) : null}
      </div>
    </section>
  );
});
