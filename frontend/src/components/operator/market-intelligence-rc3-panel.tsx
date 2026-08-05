"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Radar } from "lucide-react";
import { DeskEmpty, DeskSkeleton } from "@/components/desk/primitives";
import { Badge } from "@/components/ui/badge";
import { signalCenterApi, signalIntelligenceApi } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { classifyAsset } from "@/lib/operator/asset-class";
import { formatNumber } from "@/lib/utils";
import { cn } from "@/lib/utils";

/** RC3 Market Intelligence strip — LIVE signals / heatmap / opportunities. */
export function MarketIntelligenceRc3Panel() {
  const signalsQ = useQuery({
    queryKey: ["signals-center", "rc3-mi"],
    queryFn: () => signalCenterApi.list({}),
    staleTime: 30_000,
    refetchInterval: 60_000,
    retry: false,
  });
  const heatQ = useQuery({
    queryKey: ["si-heatmap", "rc3-mi"],
    queryFn: () => signalIntelligenceApi.heatmap(),
    staleTime: 60_000,
    refetchInterval: 120_000,
    retry: false,
  });
  const overviewQ = useQuery({
    queryKey: ["si-overview", "rc3-mi"],
    queryFn: () => signalIntelligenceApi.overview(7),
    staleTime: 60_000,
    refetchInterval: 120_000,
    retry: false,
  });

  const signals = useMemo(
    () =>
      asList(
        asRecord(signalsQ.data).items ||
          asRecord(signalsQ.data).signals ||
          signalsQ.data,
      ).map(asRecord),
    [signalsQ.data],
  );

  const breadth = useMemo(() => {
    let buy = 0;
    let sell = 0;
    for (const s of signals) {
      const d = str(s.direction || s.side).toUpperCase();
      if (d.includes("BUY") || d === "LONG") buy += 1;
      else if (d.includes("SELL") || d === "SHORT") sell += 1;
    }
    return { buy, sell, total: signals.length };
  }, [signals]);

  const trending = useMemo(() => {
    return [...signals]
      .sort(
        (a, b) =>
          num(b.quality ?? b.quality_score ?? b.confidence, 0) -
          num(a.quality ?? a.quality_score ?? a.confidence, 0),
      )
      .slice(0, 8);
  }, [signals]);

  const risks = useMemo(() => {
    return [...signals]
      .filter((s) => {
        const vol = num(s.volatility ?? s.atr ?? s.spread, NaN);
        const q = num(s.quality ?? s.quality_score, NaN);
        return (Number.isFinite(vol) && vol > 0) || (Number.isFinite(q) && q < 0.4);
      })
      .slice(0, 6);
  }, [signals]);

  const byClass = useMemo(() => {
    const m = new Map<string, number>();
    for (const s of signals) {
      const cls = classifyAsset(str(s.symbol || s.code));
      m.set(cls, (m.get(cls) ?? 0) + 1);
    }
    return [...m.entries()];
  }, [signals]);

  const heatCells = asList(
    asRecord(heatQ.data).cells ||
      asRecord(heatQ.data).items ||
      asRecord(heatQ.data).heatmap ||
      heatQ.data,
  ).map(asRecord);

  const overview = asRecord(overviewQ.data);

  if (signalsQ.isLoading && !signals.length) return <DeskSkeleton rows={6} />;
  if (!signals.length && !heatCells.length) {
    return (
      <DeskEmpty
        icon={Radar}
        title="No LIVE market intelligence"
        description="Heat map, breadth, and opportunities appear when Signal Center has LIVE rows."
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <Badge tone="success" className="h-5">
          LIVE
        </Badge>
        <span className="text-[12px] text-[var(--fg-muted)]">
          Breadth {breadth.buy} buy / {breadth.sell} sell · {breadth.total} signals
        </span>
      </div>

      <dl className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {[
          ["Market Breadth", `${breadth.buy}:${breadth.sell}`],
          [
            "Volatility",
            str(overview.volatility || overview.avg_volatility, "—"),
          ],
          [
            "Session Strength",
            str(overview.best_session || overview.session_strength, "—"),
          ],
          [
            "Liquidity",
            str(overview.liquidity || overview.liquidity_score, "—"),
          ],
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

      <section className="border border-[var(--border)] bg-[var(--surface)]">
        <header className="border-b border-[var(--border)] px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          Heat map (LIVE)
        </header>
        {heatCells.length ? (
          <div className="grid gap-1 p-3 sm:grid-cols-3 lg:grid-cols-6">
            {heatCells.slice(0, 24).map((c, i) => {
              const score = num(c.score ?? c.value ?? c.heat, 0);
              return (
                <div
                  key={`${str(c.symbol || c.session)}-${i}`}
                  className={cn(
                    "border border-[var(--border)] px-2 py-2 text-[11px]",
                    score >= 0 ? "bg-[var(--success)]/10" : "bg-[var(--danger)]/10",
                  )}
                >
                  <p className="font-mono">{str(c.symbol || c.session || c.label, "—")}</p>
                  <p className="tabular text-[var(--fg-muted)]">
                    {formatNumber(score, 2)}
                  </p>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="grid gap-1 p-3 sm:grid-cols-3 lg:grid-cols-5">
            {byClass.map(([cls, n]) => (
              <div
                key={cls}
                className="border border-[var(--border)] px-2 py-2 text-[11px]"
              >
                <p className="uppercase text-[var(--fg-subtle)]">{cls}</p>
                <p className="font-mono text-[var(--fg)]">{n}</p>
              </div>
            ))}
          </div>
        )}
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="border border-[var(--border)] bg-[var(--surface)]">
          <header className="border-b border-[var(--border)] px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Top opportunities
          </header>
          <ul className="divide-y divide-[var(--border)]">
            {trending.map((s, i) => (
              <li
                key={`${str(s.symbol)}-${i}`}
                className="flex items-center justify-between gap-2 px-3 py-2 text-[12px]"
              >
                <span className="font-mono">{str(s.symbol, "—")}</span>
                <Badge tone="neutral" className="h-5 px-1.5 text-[10px]">
                  {str(s.direction || s.side, "—")}
                </Badge>
                <span className="tabular text-[var(--fg-muted)]">
                  {str(s.quality || s.confidence, "—")}
                </span>
              </li>
            ))}
          </ul>
        </section>
        <section className="border border-[var(--border)] bg-[var(--surface)]">
          <header className="border-b border-[var(--border)] px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Top risks
          </header>
          <ul className="divide-y divide-[var(--border)]">
            {risks.length ? (
              risks.map((s, i) => (
                <li
                  key={`risk-${str(s.symbol)}-${i}`}
                  className="flex items-center justify-between gap-2 px-3 py-2 text-[12px]"
                >
                  <span className="font-mono">{str(s.symbol, "—")}</span>
                  <span className="text-[var(--fg-muted)]">
                    vol/quality watch
                  </span>
                  <span className="tabular">
                    {str(s.volatility || s.quality || s.atr, "—")}
                  </span>
                </li>
              ))
            ) : (
              <li className="px-3 py-4 text-[12px] text-[var(--fg-muted)]">
                No elevated-risk rows in LIVE feed.
              </li>
            )}
          </ul>
        </section>
      </div>
    </div>
  );
}
