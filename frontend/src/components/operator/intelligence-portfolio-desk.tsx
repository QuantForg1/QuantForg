"use client";

import { useMemo } from "react";
import { DeskEmpty, DeskSkeleton } from "@/components/desk/primitives";
import { LazyBarChart, LazyEquityChart } from "@/components/charts/lazy";
import { useLiveTrades } from "@/hooks/use-live-trades";
import { asRecord, num, str } from "@/lib/desk";
import {
  ASSET_LABELS,
  classifyAsset,
  type AssetClass,
} from "@/lib/operator/asset-class";
import { inferTradeSession } from "@/lib/orders/history";
import { useTradingSession } from "@/providers/trading-session-provider";
import { formatNumber } from "@/lib/utils";
import { Briefcase } from "lucide-react";

const CLASSES: AssetClass[] = [
  "forex",
  "metals",
  "crypto",
  "energy",
  "indices",
];

/** LIVE portfolio intelligence curves & allocation — never fabricated. */
export function IntelligencePortfolioDesk() {
  const session = useTradingSession();
  const { trades, analytics, loading } = useLiveTrades("month");
  const closed = useMemo(
    () => trades.filter((t) => t.status === "closed"),
    [trades],
  );

  const equityData = useMemo(
    () =>
      analytics.equityCurve.map((p) => ({
        t: new Date(p.t).toISOString().slice(0, 10),
        equity: p.equity,
      })),
    [analytics.equityCurve],
  );

  const balanceData = useMemo(
    () =>
      analytics.balanceCurve.map((p) => ({
        t: new Date(p.t).toISOString().slice(0, 10),
        equity: p.balance,
      })),
    [analytics.balanceCurve],
  );

  const drawdownData = useMemo(() => {
    let peak = 0;
    return analytics.equityCurve.map((p) => {
      peak = Math.max(peak, p.equity);
      return {
        label: new Date(p.t).toISOString().slice(5, 10),
        value: Math.max(0, peak - p.equity),
      };
    });
  }, [analytics.equityCurve]);

  const allocation = useMemo(() => {
    const m = new Map<AssetClass, number>();
    for (const c of CLASSES) m.set(c, 0);
    for (const p of session.positions) {
      const r = asRecord(p);
      const cls = classifyAsset(str(r.symbol));
      if (!m.has(cls)) continue;
      m.set(cls, (m.get(cls) ?? 0) + Math.abs(num(r.volume ?? r.lots, 0)));
    }
    return CLASSES.map((c) => ({
      label: ASSET_LABELS[c],
      value: m.get(c) ?? 0,
    }));
  }, [session.positions]);

  const bySymbol = analytics.bySymbol;
  const bySession = analytics.bySession;
  const byStrategy = useMemo(() => {
    const m = new Map<string, number>();
    for (const t of closed) {
      const k = t.strategy || "Unspecified";
      m.set(k, (m.get(k) ?? 0) + t.netPl);
    }
    return [...m.entries()]
      .map(([label, value]) => ({ label, value }))
      .sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
      .slice(0, 12);
  }, [closed]);

  if (loading && !closed.length && !session.positions.length) {
    return <DeskSkeleton rows={8} />;
  }

  if (!closed.length && !session.positions.length) {
    return (
      <DeskEmpty
        icon={Briefcase}
        title="No LIVE portfolio sample"
        description="Equity, drawdown, and allocation appear from closed deals and open positions."
      />
    );
  }

  return (
    <div className="space-y-5">
      <dl className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {[
          ["Open Exposure", String(session.positions.length)],
          [
            "Float PnL",
            formatNumber(
              session.positions.reduce(
                (s, p) => s + num(asRecord(p).profit, 0),
                0,
              ),
              2,
            ),
          ],
          [
            "Max Drawdown",
            analytics.maxDrawdown != null
              ? formatNumber(analytics.maxDrawdown, 2)
              : "—",
          ],
          ["Closed Trades", String(closed.length)],
        ].map(([k, v]) => (
          <div
            key={k}
            className="border border-[var(--border)] bg-[var(--surface)] px-3 py-2"
          >
            <dt className="text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
              {k}
            </dt>
            <dd className="mt-1 font-mono text-[14px] text-[var(--fg)]">{v}</dd>
          </div>
        ))}
      </dl>

      <div className="grid gap-4 xl:grid-cols-2">
        <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
          <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Equity curve
          </h3>
          <LazyEquityChart data={equityData} emptyLabel="No equity path yet" />
        </section>
        <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
          <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Balance curve
          </h3>
          <LazyEquityChart
            data={balanceData}
            emptyLabel="No balance path yet"
            color="var(--fg-muted)"
          />
        </section>
        <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
          <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Drawdown curve
          </h3>
          <LazyBarChart data={drawdownData} />
        </section>
        <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
          <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Asset allocation
          </h3>
          <LazyBarChart data={allocation} />
        </section>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
          <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            PnL by symbol
          </h3>
          <LazyBarChart data={bySymbol.slice(0, 12)} />
        </section>
        <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
          <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            PnL by strategy
          </h3>
          <LazyBarChart data={byStrategy} />
        </section>
        <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
          <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            PnL by session
          </h3>
          <LazyBarChart
            data={
              bySession.length
                ? bySession
                : closed.reduce<{ label: string; value: number }[]>((acc, t) => {
                    const label = inferTradeSession(t.time);
                    const hit = acc.find((x) => x.label === label);
                    if (hit) hit.value += t.netPl;
                    else acc.push({ label, value: t.netPl });
                    return acc;
                  }, [])
            }
          />
        </section>
      </div>
    </div>
  );
}
