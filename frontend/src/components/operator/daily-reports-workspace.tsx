"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { FileText } from "lucide-react";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { Button } from "@/components/ui/button";
import { useLiveTrades } from "@/hooks/use-live-trades";
import { ecosystemApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import {
  downloadText,
  exportPrintablePdf,
  kvTable,
  toCsv,
} from "@/lib/operator/export";
import { inferTradeSession, type HistoryRange } from "@/lib/orders/history";
import { formatNumber } from "@/lib/utils";

type Period = "daily" | "weekly" | "monthly";

function periodToRange(p: Period): HistoryRange {
  if (p === "daily") return "today";
  if (p === "weekly") return "week";
  return "month";
}

/** Daily / weekly / monthly institutional reports from LIVE trades + ecosystem reports. */
export function DailyReportsWorkspace() {
  const [period, setPeriod] = useState<Period>("daily");
  const { trades, analytics, loading, error, refetch } = useLiveTrades(
    periodToRange(period),
  );
  const reportQ = useQuery({
    queryKey: ["ecosystem-reports", period, "operator"],
    queryFn: () => ecosystemApi.reports(period),
    staleTime: 30_000,
    retry: false,
  });

  const closed = useMemo(
    () => trades.filter((t) => t.status === "closed"),
    [trades],
  );
  const wins = closed.filter((t) => t.netPl > 0);
  const losses = closed.filter((t) => t.netPl < 0);
  const pnl = closed.reduce((s, t) => s + t.netPl, 0);

  const byStrategy = useMemo(() => {
    const m = new Map<string, number>();
    for (const t of closed) {
      const k = t.strategy || "Unspecified";
      m.set(k, (m.get(k) ?? 0) + t.netPl);
    }
    return [...m.entries()].sort((a, b) => b[1] - a[1]);
  }, [closed]);

  const bySession = useMemo(() => {
    const m = new Map<string, number>();
    for (const t of closed) {
      const k = inferTradeSession(t.time);
      m.set(k, (m.get(k) ?? 0) + t.netPl);
    }
    return [...m.entries()].sort((a, b) => b[1] - a[1]);
  }, [closed]);

  const bySymbol = analytics.bySymbol;

  const metrics: Array<[string, string]> = [
    ["Trades", String(closed.length)],
    ["Wins", String(wins.length)],
    ["Losses", String(losses.length)],
    ["PnL", formatNumber(pnl, 2)],
    ["Drawdown", analytics.maxDrawdown != null ? formatNumber(analytics.maxDrawdown, 2) : "—"],
    ["Win Rate", analytics.winRate != null ? `${(analytics.winRate * 100).toFixed(1)}%` : "—"],
    [
      "Profit Factor",
      analytics.profitFactor != null ? formatNumber(analytics.profitFactor, 2) : "—",
    ],
    [
      "Average RR",
      analytics.averageRr != null ? formatNumber(analytics.averageRr, 2) : "—",
    ],
    [
      "Average Hold",
      analytics.avgHoldMs != null
        ? `${Math.round(analytics.avgHoldMs / 60000)}m`
        : "—",
    ],
    ["Best Symbol", bySymbol[0]?.label || "—"],
    ["Worst Symbol", bySymbol[bySymbol.length - 1]?.label || "—"],
    ["Best Session", bySession[0]?.[0] || "—"],
    ["Worst Session", bySession[bySession.length - 1]?.[0] || "—"],
    ["Best Strategy", byStrategy[0]?.[0] || "—"],
    ["Worst Strategy", byStrategy[byStrategy.length - 1]?.[0] || "—"],
    [
      "Largest Win",
      analytics.largestWin != null ? formatNumber(analytics.largestWin, 2) : "—",
    ],
    [
      "Largest Loss",
      analytics.largestLoss != null ? formatNumber(analytics.largestLoss, 2) : "—",
    ],
    [
      "Largest Drawdown",
      analytics.maxDrawdown != null ? formatNumber(analytics.maxDrawdown, 2) : "—",
    ],
    [
      "Largest Recovery",
      analytics.recoveryFactor != null
        ? formatNumber(analytics.recoveryFactor, 2)
        : "—",
    ],
  ];

  if (loading && !closed.length) return <DeskSkeleton rows={8} />;
  if (error && !closed.length) {
    return (
      <DeskError
        message="Unable to load LIVE report window."
        onRetry={() => void refetch()}
      />
    );
  }

  const eco = asRecord(reportQ.data);
  const sections = asRecord(eco.sections);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex gap-1">
          {(["daily", "weekly", "monthly"] as const).map((p) => (
            <Button
              key={p}
              size="sm"
              variant={period === p ? "default" : "outline"}
              onClick={() => setPeriod(p)}
            >
              {p}
            </Button>
          ))}
        </div>
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() =>
              downloadText(
                `quantforg-${period}-report.csv`,
                toCsv(metrics.map(([k, v]) => ({ metric: k, value: v }))),
                "text/csv",
              )
            }
          >
            CSV
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() =>
              exportPrintablePdf({
                title: `${period[0]!.toUpperCase()}${period.slice(1)} Trading Report`,
                subtitle: `Generated ${new Date().toISOString()} · LIVE fills only`,
                sections: [
                  { heading: "Summary", html: kvTable(metrics) },
                  {
                    heading: "Ops notes",
                    html: `<p>${str(asList(sections.recommendations)[0] as string, "No ops recommendations in feed.")}</p>`,
                  },
                ],
              })
            }
          >
            <FileText className="mr-1 h-3.5 w-3.5" />
            PDF
          </Button>
        </div>
      </div>

      {!closed.length ? (
        <DeskEmpty
          icon={FileText}
          title={`No ${period} trades`}
          description="Report metrics populate from LIVE closed deals in the selected window."
        />
      ) : (
        <dl className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {metrics.map(([k, v]) => (
            <div
              key={k}
              className="border border-[var(--border)] bg-[var(--surface)] px-3 py-2"
            >
              <dt className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                {k}
              </dt>
              <dd className="mt-1 font-mono text-[14px] text-[var(--fg)]">{v}</dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  );
}
