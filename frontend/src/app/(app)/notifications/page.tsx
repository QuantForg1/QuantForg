"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, CheckCheck, Search } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { PageMotion } from "@/components/desk/motion";
import { platformApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, str } from "@/lib/desk";
import { formatRelativeTime } from "@/lib/utils";

const SECTIONS = ["all", "trading", "risk", "system", "execution"] as const;

export default function NotificationsPage() {
  const qc = useQueryClient();
  const [section, setSection] = useState<(typeof SECTIONS)[number]>("all");
  const [q, setQ] = useState("");
  const [unreadOnly, setUnreadOnly] = useState(false);

  const list = useQuery({
    queryKey: ["notifications", unreadOnly],
    queryFn: () => platformApi.notifications(unreadOnly),
    retry: false,
  });

  const mark = useMutation({
    mutationFn: platformApi.markNotificationRead,
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["notifications"] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Mark read failed"),
  });

  const allItems = useMemo(() => asList(list.data).map(asRecord), [list.data]);
  const unreadCount = allItems.filter((n) => !n.is_read).length;

  const items = useMemo(() => {
    return allItems.filter((n) => {
      const cat = str(n.category, "").toLowerCase();
      if (section !== "all" && !cat.includes(section)) return false;
      if (!q.trim()) return true;
      const hay = `${str(n.title)} ${str(n.body)}`.toLowerCase();
      return hay.includes(q.trim().toLowerCase());
    });
  }, [allItems, section, q]);

  const grouped = useMemo(() => {
    const map = new Map<string, typeof items>();
    for (const n of items) {
      const key = str(n.category, "system").toLowerCase();
      const bucket = map.get(key) ?? [];
      bucket.push(n);
      map.set(key, bucket);
    }
    return [...map.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [items]);

  const markAll = async () => {
    const unread = items.filter((n) => !n.is_read);
    if (!unread.length) {
      toast.message("Nothing unread");
      return;
    }
    try {
      await Promise.all(unread.map((n) => platformApi.markNotificationRead(str(n.id))));
      toast.success(`Marked ${unread.length} as read`);
      await qc.invalidateQueries({ queryKey: ["notifications"] });
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Mark all failed");
    }
  };

  return (
    <div>
      <PageHeader
        title="Notifications"
        description="Trading, risk, system, and execution inbox."
        actions={
          <>
            {unreadCount > 0 ? (
              <Badge tone="accent" aria-label={`${unreadCount} unread`}>
                {unreadCount} unread
              </Badge>
            ) : null}
            <Button
              size="sm"
              variant="secondary"
              onClick={markAll}
              disabled={!unreadCount}
              aria-label="Mark all as read"
            >
              <CheckCheck className="h-3.5 w-3.5" />
              Mark all read
            </Button>
            <Button
              size="sm"
              variant={unreadOnly ? "default" : "ghost"}
              onClick={() => setUnreadOnly((v) => !v)}
            >
              {unreadOnly ? "Unread only" : "All messages"}
            </Button>
          </>
        }
      />

      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Notification categories">
          {SECTIONS.map((s) => (
            <Button
              key={s}
              size="sm"
              role="tab"
              aria-selected={section === s}
              variant={section === s ? "default" : "ghost"}
              onClick={() => setSection(s)}
              className="capitalize"
            >
              {s}
            </Button>
          ))}
        </div>
        <div className="relative w-full sm:w-72">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--fg-subtle)]"
            aria-hidden
          />
          <Input
            className="pl-9"
            placeholder="Search inbox…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            aria-label="Search notifications"
          />
        </div>
      </div>

      {list.isLoading ? (
        <DeskSkeleton rows={5} />
      ) : list.isError ? (
        <DeskError message="Unable to load notifications." onRetry={() => list.refetch()} />
      ) : items.length === 0 ? (
        <DeskEmpty
          icon={Bell}
          title="Inbox clear"
          description="No notifications match this filter."
        />
      ) : (
        <PageMotion className="space-y-6">
          {grouped.map(([category, rows]) => (
            <section key={category} aria-label={`${category} notifications`}>
              <div className="mb-2 flex items-center gap-2">
                <h2 className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                  {category}
                </h2>
                <Badge tone="neutral">{rows.length}</Badge>
              </div>
              <div className="space-y-2">
                {rows.map((n) => {
                  const unread = !n.is_read;
                  return (
                    <Card
                      key={str(n.id)}
                      className={
                        unread
                          ? "border-[var(--accent)]/35 bg-[var(--accent-soft)]/25 qf-card-interactive"
                          : "qf-card-interactive"
                      }
                    >
                      <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-start sm:justify-between">
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="font-medium text-[var(--fg)]">{str(n.title)}</p>
                            {unread ? <Badge tone="success">Unread</Badge> : null}
                          </div>
                          <p className="mt-1 text-sm text-[var(--fg-muted)]">{str(n.body)}</p>
                          <p className="mt-2 text-xs text-[var(--fg-subtle)]">
                            {formatRelativeTime(str(n.created_at))}
                          </p>
                        </div>
                        {unread ? (
                          <Button
                            size="sm"
                            variant="secondary"
                            disabled={mark.isPending}
                            onClick={() => mark.mutate(str(n.id))}
                          >
                            Mark read
                          </Button>
                        ) : null}
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </section>
          ))}
        </PageMotion>
      )}
    </div>
  );
}
