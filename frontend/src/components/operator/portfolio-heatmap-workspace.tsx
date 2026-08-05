"use client";

import { useMemo } from "react";
import { Layers3 } from "lucide-react";
import { DeskEmpty } from "@/components/desk/primitives";
import { Badge } from "@/components/ui/badge";
import { useTradingSession } from "@/providers/trading-session-provider";
import { asRecord, num, str } from "@/lib/desk";
import {
  ASSET_LABELS,
  classifyAsset,
  type AssetClass,
} from "@/lib/operator/asset-class";
import { formatNumber } from "@/lib/utils";
import { cn } from "@/lib/utils";

const CLASSES: AssetClass[] = [
  "forex",
  "crypto",
  "metals",
  "indices",
  "energy",
];

/** Realtime portfolio heatmap by asset class — LIVE positions only. */
export function PortfolioHeatmapWorkspace() {
  const session = useTradingSession();
  const positions = session.positions;

  const cells = useMemo(() => {
    const buckets = new Map<
      AssetClass,
      { exposure: number; pnl: number; count: number; symbols: string[] }
    >();
    for (const c of CLASSES) {
      buckets.set(c, { exposure: 0, pnl: 0, count: 0, symbols: [] });
    }
    for (const raw of positions) {
      const p = asRecord(raw);
      const symbol = str(p.symbol).toUpperCase();
      const cls = classifyAsset(symbol);
      if (cls === "other") continue;
      const b = buckets.get(cls)!;
      const vol = Math.abs(num(p.volume ?? p.lots, 0));
      const pnl = num(p.profit, 0);
      b.exposure += vol;
      b.pnl += pnl;
      b.count += 1;
      if (symbol && !b.symbols.includes(symbol)) b.symbols.push(symbol);
    }
    return CLASSES.map((c) => ({ id: c, ...buckets.get(c)! }));
  }, [positions]);

  const totalPnl = cells.reduce((s, c) => s + c.pnl, 0);
  const maxAbs = Math.max(1, ...cells.map((c) => Math.abs(c.pnl)));

  if (!positions.length) {
    return (
      <DeskEmpty
        icon={Layers3}
        title="No open exposure"
        description="Heatmap cells populate from LIVE open positions across Forex, Crypto, Metals, Indices, Energy."
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Badge tone={session.connected ? "success" : "warning"} className="h-5">
          {session.connected ? "Realtime" : "Session"}
        </Badge>
        <p className="text-[12px] text-[var(--fg-muted)]">
          Float PnL {formatNumber(totalPnl, 2)} · {positions.length} positions
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        {cells.map((c) => {
          const intensity = Math.abs(c.pnl) / maxAbs;
          const positive = c.pnl >= 0;
          return (
            <section
              key={c.id}
              className={cn(
                "border border-[var(--border)] px-3 py-3",
                c.count ? "bg-[var(--surface)]" : "bg-[var(--bg)] opacity-70",
              )}
              style={{
                boxShadow: c.count
                  ? `inset 0 0 0 1px ${positive ? `rgba(34,197,94,${0.15 + intensity * 0.45})` : `rgba(239,68,68,${0.15 + intensity * 0.45})`}`
                  : undefined,
              }}
            >
              <header className="flex items-center justify-between gap-2">
                <h3 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
                  {ASSET_LABELS[c.id]}
                </h3>
                <Badge tone={c.count ? (positive ? "success" : "danger") : "neutral"} className="h-5">
                  {c.count ? "Live" : "Flat"}
                </Badge>
              </header>
              <dl className="mt-2 grid grid-cols-2 gap-1 text-[11px]">
                <dt className="text-[var(--fg-subtle)]">Exposure</dt>
                <dd className="tabular text-[var(--fg)]">{formatNumber(c.exposure, 2)}</dd>
                <dt className="text-[var(--fg-subtle)]">PnL</dt>
                <dd
                  className={cn(
                    "tabular",
                    positive ? "text-[var(--success)]" : "text-[var(--danger)]",
                  )}
                >
                  {formatNumber(c.pnl, 2)}
                </dd>
                <dt className="text-[var(--fg-subtle)]">Risk</dt>
                <dd className="tabular text-[var(--fg)]">{c.count} pos</dd>
                <dt className="text-[var(--fg-subtle)]">Allocation</dt>
                <dd className="tabular text-[var(--fg)]">
                  {positions.length
                    ? `${((c.count / positions.length) * 100).toFixed(0)}%`
                    : "—"}
                </dd>
              </dl>
              <p className="mt-2 truncate font-mono text-[10px] text-[var(--fg-muted)]">
                {c.symbols.join(" · ") || "—"}
              </p>
            </section>
          );
        })}
      </div>
    </div>
  );
}
