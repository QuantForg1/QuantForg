"use client";

import Link from "next/link";
import { Bell } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { str } from "@/lib/desk";
import { formatRelativeTime } from "@/lib/utils";

export type DashboardNotification = {
  id: string;
  title: string;
  body?: string;
  createdAt?: string;
  unread?: boolean;
  category?: string;
};

export function NotificationsStrip({
  items,
  unavailable,
}: {
  items: DashboardNotification[];
  unavailable?: boolean;
}) {
  const unread = items.filter((n) => n.unread).length;

  return (
    <section
      aria-labelledby="dashboard-notifications"
      className="space-y-3 rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] p-4 shadow-[var(--shadow-card)]"
    >
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2
              id="dashboard-notifications"
              className="text-sm font-medium text-[var(--fg)]"
            >
              Notifications
            </h2>
            {unread > 0 ? <Badge tone="warning">{unread} unread</Badge> : null}
          </div>
          <p className="mt-1 text-xs text-[var(--fg-muted)]">
            Broker, robot, risk, and execution alerts for your account inbox.
          </p>
        </div>
        <Button variant="ghost" size="sm" asChild>
          <Link href="/notifications">
            <Bell className="h-3.5 w-3.5" /> Inbox
          </Link>
        </Button>
      </div>

      {unavailable ? (
        <p className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--bg)]/40 px-3 py-3 text-sm text-[var(--fg-muted)]">
          Notifications are temporarily unavailable.
        </p>
      ) : items.length === 0 ? (
        <p className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--bg)]/40 px-3 py-3 text-sm text-[var(--fg-muted)]">
          No recent notifications.
        </p>
      ) : (
        <ul className="space-y-2">
          {items.slice(0, 5).map((n) => (
            <li
              key={n.id}
              className="flex min-w-0 items-start justify-between gap-3 rounded-[var(--radius-os)] border border-[var(--border)] px-3 py-2"
            >
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-[var(--fg)]">
                  {n.title}
                </p>
                {n.body ? (
                  <p className="mt-0.5 line-clamp-2 text-xs text-[var(--fg-muted)]">
                    {n.body}
                  </p>
                ) : null}
              </div>
              <span className="shrink-0 text-[11px] text-[var(--fg-subtle)]">
                {n.createdAt ? formatRelativeTime(n.createdAt) : "—"}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function mapPlatformNotifications(
  rows: Record<string, unknown>[],
): DashboardNotification[] {
  return rows.map((row, i) => ({
    id: str(row.id, String(i)),
    title: str(row.title ?? row.subject ?? row.category, "Notification"),
    body: str(row.body ?? row.message ?? row.detail, "") || undefined,
    createdAt: str(row.created_at ?? row.createdAt ?? row.timestamp, ""),
    unread: !(row.read === true || row.is_read === true),
    category: str(row.category, ""),
  }));
}
