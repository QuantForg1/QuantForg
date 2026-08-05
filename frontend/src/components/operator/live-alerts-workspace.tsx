"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Bell, Mail, MonitorSmartphone } from "lucide-react";
import { toast } from "sonner";
import { DeskEmpty, DeskSkeleton } from "@/components/desk/primitives";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ecosystemApi, platformApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { useNotificationsStream } from "@/hooks/realtime";
import { formatRelativeTime } from "@/lib/utils";

const PREF_KEY = "qf.operator.alert.prefs.v1";

type Prefs = {
  desktop: boolean;
  email: string;
  telegramChatId: string;
};

function loadPrefs(): Prefs {
  try {
    const raw = localStorage.getItem(PREF_KEY);
    if (raw) return JSON.parse(raw) as Prefs;
  } catch {
    /* ignore */
  }
  return { desktop: false, email: "", telegramChatId: "" };
}

/**
 * Live Alerts — desktop / email / Telegram-ready architecture.
 * Alerts only — never executes trades.
 */
export function LiveAlertsWorkspace() {
  const realtime = useNotificationsStream();
  const [prefs, setPrefs] = useState<Prefs>({ desktop: false, email: "", telegramChatId: "" });
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setPrefs(loadPrefs());
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    try {
      localStorage.setItem(PREF_KEY, JSON.stringify(prefs));
    } catch {
      /* ignore */
    }
  }, [hydrated, prefs]);

  const listQ = useQuery({
    queryKey: ["notifications", "live-alerts"],
    queryFn: () => platformApi.notifications(false),
    staleTime: 10_000,
    refetchInterval: 20_000,
    retry: false,
  });
  const ecoQ = useQuery({
    queryKey: ["ecosystem-alerts"],
    queryFn: () => ecosystemApi.alerts(),
    staleTime: 20_000,
    refetchInterval: 30_000,
    retry: false,
  });

  const items = useMemo(() => {
    const platform = asList(listQ.data).map((n) => {
      const r = asRecord(n);
      return {
        id: str(r.id),
        title: str(r.title, "Alert"),
        body: str(r.body || r.message, ""),
        category: str(r.category, "system"),
        at: str(r.created_at || r.timestamp, ""),
        source: "platform",
      };
    });
    const eco = asList(
      asRecord(ecoQ.data).items || asRecord(ecoQ.data).alerts || ecoQ.data,
    ).map((n, i) => {
      const r = asRecord(n);
      return {
        id: str(r.id, `eco-${i}`),
        title: str(r.title || r.type || "Ecosystem alert"),
        body: str(r.body || r.message || r.detail, ""),
        category: str(r.category || r.kind, "ops"),
        at: str(r.created_at || r.at || r.timestamp, ""),
        source: "ecosystem",
      };
    });
    return [...platform, ...eco].slice(0, 120);
  }, [ecoQ.data, listQ.data]);

  // Desktop push for newest unread-style item when enabled.
  useEffect(() => {
    if (!prefs.desktop || typeof window === "undefined" || !("Notification" in window)) {
      return;
    }
    if (Notification.permission !== "granted") return;
    const latest = items[0];
    if (!latest?.title) return;
    const key = `qf.alert.shown.${latest.id}`;
    if (sessionStorage.getItem(key)) return;
    sessionStorage.setItem(key, "1");
    try {
      new Notification(latest.title, { body: latest.body.slice(0, 140) });
    } catch {
      /* ignore */
    }
  }, [items, prefs.desktop]);

  const enableDesktop = async () => {
    if (!("Notification" in window)) {
      toast.error("Desktop notifications not supported in this browser");
      return;
    }
    const perm = await Notification.requestPermission();
    if (perm !== "granted") {
      toast.error("Desktop notifications denied");
      return;
    }
    setPrefs((p) => ({ ...p, desktop: true }));
    toast.success("Desktop alerts enabled");
  };

  if (listQ.isLoading && ecoQ.isLoading && !items.length) {
    return <DeskSkeleton rows={6} />;
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="warning" className="h-5">
          Alerts only — no execution
        </Badge>
        <Badge tone="neutral" className="h-5">
          Stream {realtime.transport}
            {realtime.connected ? " · live" : " · polling"}
        </Badge>
      </div>

      <section className="grid gap-3 lg:grid-cols-3">
        <div className="border border-[var(--border)] bg-[var(--surface)] px-3 py-3">
          <div className="mb-2 flex items-center gap-2 text-[12px] font-medium text-[var(--fg)]">
            <MonitorSmartphone className="h-4 w-4 text-[var(--accent)]" />
            Desktop
          </div>
          <p className="mb-2 text-[11px] text-[var(--fg-muted)]">
            Browser push notifications for new LIVE alerts.
          </p>
          <Button
            size="sm"
            variant={prefs.desktop ? "secondary" : "outline"}
            onClick={() => void enableDesktop()}
          >
            {prefs.desktop ? "Enabled" : "Enable desktop"}
          </Button>
        </div>
        <div className="border border-[var(--border)] bg-[var(--surface)] px-3 py-3">
          <div className="mb-2 flex items-center gap-2 text-[12px] font-medium text-[var(--fg)]">
            <Mail className="h-4 w-4 text-[var(--accent)]" />
            Email (ready)
          </div>
          <Input
            value={prefs.email}
            onChange={(e) => setPrefs((p) => ({ ...p, email: e.target.value }))}
            placeholder="ops@firm.com"
            className="mb-2"
          />
          <p className="text-[11px] text-[var(--fg-subtle)]">
            Address stored client-side for future mailer wiring — no send from UI.
          </p>
        </div>
        <div className="border border-[var(--border)] bg-[var(--surface)] px-3 py-3">
          <div className="mb-2 flex items-center gap-2 text-[12px] font-medium text-[var(--fg)]">
            <Bell className="h-4 w-4 text-[var(--accent)]" />
            Telegram-ready
          </div>
          <Input
            value={prefs.telegramChatId}
            onChange={(e) =>
              setPrefs((p) => ({ ...p, telegramChatId: e.target.value }))
            }
            placeholder="Chat ID"
            className="mb-2"
          />
          <p className="text-[11px] text-[var(--fg-subtle)]">
            Architecture ready — chat id captured; bot delivery is a future ops hook.
          </p>
        </div>
      </section>

      {!items.length ? (
        <DeskEmpty
          icon={Bell}
          title="No live alerts"
          description="Signals, orders, risk, gateway, broker, portfolio, reports, and errors appear here from LIVE feeds."
        />
      ) : (
        <ul className="divide-y divide-[var(--border)] border border-[var(--border)] bg-[var(--surface)]">
          {items.map((n) => (
            <li key={`${n.source}-${n.id}`} className="px-3 py-2.5">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[13px] font-medium text-[var(--fg)]">{n.title}</span>
                <Badge tone="neutral" className="h-5 px-1.5 text-[10px]">
                  {n.category}
                </Badge>
                <span className="text-[10px] text-[var(--fg-subtle)]">
                  {n.at ? formatRelativeTime(n.at) : n.source}
                </span>
              </div>
              {n.body ? (
                <p className="mt-1 text-[12px] text-[var(--fg-muted)]">{n.body}</p>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
