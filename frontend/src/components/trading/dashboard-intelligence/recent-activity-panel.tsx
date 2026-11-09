"use client";

import Link from "next/link";
import { Activity, Layers } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskEmpty } from "@/components/desk/primitives";
import { num, str } from "@/lib/desk";
import { positionExposureLabel } from "@/lib/trading/trader-ux";
import { cn, formatCurrency, formatRelativeTime } from "@/lib/utils";

export type ActivityItem = {
  id: string;
  kind: "opened" | "closed" | "rejected" | "risk" | "execution";
  title: string;
  detail?: string;
  pnl?: number;
  at?: string;
};

function kindTone(
  kind: ActivityItem["kind"],
): "success" | "warning" | "danger" | "neutral" {
  if (kind === "opened") return "success";
  if (kind === "closed") return "neutral";
  if (kind === "rejected" || kind === "risk") return "danger";
  return "warning";
}

export function buildActivityFromAccount(opts: {
  positions: Record<string, unknown>[];
  deals: Record<string, unknown>[];
  riskState?: string;
  riskReason?: string;
}): ActivityItem[] {
  const items: ActivityItem[] = [];

  for (const p of opts.positions.slice(0, 4)) {
    items.push({
      id: `pos-${str(p.ticket, str(p.id, Math.random().toString(36).slice(2)))}`,
      kind: "opened",
      title: `${str(p.symbol)} ${positionExposureLabel(p.side)} open`,
      detail: `Vol ${str(p.volume, "—")}`,
      pnl: num(p.profit),
      at: str(p.open_time ?? p.time, ""),
    });
  }

  for (const d of opts.deals.slice(0, 6)) {
    const pnl = num(d.profit);
    const rejected = /reject|denied|blocked/i.test(
      str(d.status ?? d.comment ?? d.reason, ""),
    );
    items.push({
      id: `deal-${str(d.ticket, str(d.id, Math.random().toString(36).slice(2)))}`,
      kind: rejected ? "rejected" : "closed",
      title: rejected
        ? `${str(d.symbol)} execution rejected`
        : `${str(d.symbol)} ${positionExposureLabel(d.side)} closed`,
      detail: rejected
        ? str(d.comment ?? d.reason ?? d.status, "Rejected by broker/OMS")
        : undefined,
      pnl: Number.isFinite(pnl) ? pnl : undefined,
      at: str(d.time ?? d.close_time, ""),
    });
  }

  if (opts.riskState && opts.riskState !== "Healthy" && opts.riskReason) {
    items.unshift({
      id: "risk-event",
      kind: "risk",
      title: `Risk ${opts.riskState}`,
      detail: opts.riskReason,
      at: new Date().toISOString(),
    });
  }

  return items
    .sort((a, b) => Date.parse(b.at || "0") - Date.parse(a.at || "0"))
    .slice(0, 8);
}

export function RecentActivityPanel({
  items,
  unavailable,
  noBroker,
}: {
  items: ActivityItem[];
  unavailable?: boolean;
  noBroker?: boolean;
}) {
  return (
    <section
      aria-labelledby="recent-trading-activity"
      className="space-y-3 rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] p-4 shadow-[var(--shadow-card)]"
    >
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2
            id="recent-trading-activity"
            className="text-sm font-medium text-[var(--fg)]"
          >
            Recent Trading Activity
          </h2>
          <p className="mt-1 text-xs text-[var(--fg-muted)]">
            Positions, fills, and risk events for your authorized account only.
          </p>
        </div>
        <div className="flex gap-1">
          <Button variant="ghost" size="sm" asChild>
            <Link href="/positions">Positions</Link>
          </Button>
          <Button variant="ghost" size="sm" asChild>
            <Link href="/journal">History</Link>
          </Button>
        </div>
      </div>

      {noBroker ? (
        <DeskEmpty
          icon={Layers}
          title="No broker connected"
          description="Connect your broker to load account activity."
          actionLabel="Connect Broker"
          actionHref="/broker"
        />
      ) : unavailable ? (
        <DeskEmpty
          icon={Activity}
          title="Activity unavailable"
          description="Your account history could not be loaded. This is not an empty history."
        />
      ) : items.length === 0 ? (
        <DeskEmpty
          icon={Activity}
          title="No recent activity"
          description="No recent positions, fills, or risk events for this account."
        />
      ) : (
        <ul className="space-y-2">
          {items.map((item) => (
            <li
              key={item.id}
              className="flex min-w-0 flex-wrap items-center justify-between gap-2 rounded-[var(--radius-os)] border border-[var(--border)] px-3 py-2 text-sm"
            >
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={kindTone(item.kind)}>{item.kind}</Badge>
                  <span className="truncate font-medium text-[var(--fg)]">
                    {item.title}
                  </span>
                </div>
                {item.detail ? (
                  <p className="mt-0.5 truncate text-xs text-[var(--fg-muted)]">
                    {item.detail}
                  </p>
                ) : null}
              </div>
              {item.pnl != null && Number.isFinite(item.pnl) ? (
                <span
                  className={cn(
                    "tabular",
                    item.pnl >= 0
                      ? "text-[var(--success)]"
                      : "text-[var(--danger)]",
                  )}
                >
                  {formatCurrency(item.pnl)}
                </span>
              ) : null}
              <span className="shrink-0 text-xs text-[var(--fg-subtle)]">
                {item.at ? formatRelativeTime(item.at) : "—"}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
