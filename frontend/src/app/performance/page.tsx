"use client";

import { useQuery } from "@tanstack/react-query";
import { PricingFooter, PricingHeader } from "@/components/pricing/marketing-chrome";
import { apiFetch } from "@/lib/api/client";

type Summary = {
  trades: number;
  wins: number;
  losses: number;
  breakeven: number;
  win_rate_pct: number | null;
  net_pnl_usd: number;
  profit_factor: number | null;
  avg_r: number | null;
};
type Perf = {
  available: boolean;
  generated_at?: string;
  all_time?: Summary;
  last_30_days?: Summary;
  last_7_days?: Summary;
  recent?: { opened_at: string; side: string; result_r: number | null; outcome: string }[];
  disclosure?: string;
};

const dash = (v: number | null | undefined, suffix = "") =>
  v === null || v === undefined ? "—" : `${v}${suffix}`;

function Card({ title, s }: { title: string; s?: Summary }) {
  return (
    <section className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
      <h2 className="text-sm font-semibold text-[var(--muted)]">{title}</h2>
      <p className="mt-2 text-3xl font-semibold tabular-nums">{s ? s.trades : "—"}</p>
      <p className="text-xs text-[var(--muted)]">closed trades</p>
      <dl className="mt-4 grid grid-cols-2 gap-2 text-sm">
        <dt className="text-[var(--muted)]">Wins / Losses</dt>
        <dd className="text-right tabular-nums">{s ? `${s.wins} / ${s.losses}` : "—"}</dd>
        <dt className="text-[var(--muted)]">Win rate</dt>
        <dd className="text-right tabular-nums">{dash(s?.win_rate_pct, "%")}</dd>
        <dt className="text-[var(--muted)]">Profit factor</dt>
        <dd className="text-right tabular-nums">{dash(s?.profit_factor)}</dd>
        <dt className="text-[var(--muted)]">Average R</dt>
        <dd className="text-right tabular-nums">{dash(s?.avg_r)}</dd>
        <dt className="text-[var(--muted)]">Net (0.01 lot)</dt>
        <dd className="text-right tabular-nums">
          {s ? `${s.net_pnl_usd >= 0 ? "+" : "-"}$${Math.abs(s.net_pnl_usd).toFixed(2)}` : "—"}
        </dd>
      </dl>
    </section>
  );
}

export default function PerformancePage() {
  const q = useQuery({
    queryKey: ["public-performance"],
    queryFn: () => apiFetch<Perf>("/public/market/performance", { auth: false }),
    retry: 1,
    refetchInterval: 300_000,
  });
  const d = q.data;
  return (
    <div className="min-h-screen bg-[var(--bg)] text-[var(--fg)]">
      <PricingHeader active="home" />
      <main id="main-content" className="mx-auto w-full max-w-5xl px-4 pb-16 pt-10 sm:px-6">
        <h1 className="text-3xl font-semibold tracking-tight">Live track record</h1>
        <p className="mt-2 max-w-2xl text-[var(--muted)]">
          Every closed XAUUSD trade, wins and losses, from the real journal. Nothing is
          filtered out. Results are in R (multiples of the planned risk) and in dollars at
          the minimum 0.01 lot.
        </p>
        {q.isLoading ? <p className="mt-8 text-sm">Loading…</p> : null}
        {d && !d.available ? (
          <p className="mt-8 text-sm text-[var(--muted)]">
            Track record is temporarily unavailable. Please try again shortly.
          </p>
        ) : null}
        {d?.available ? (
          <>
            <div className="mt-8 grid gap-4 sm:grid-cols-3">
              <Card title="Last 7 days" s={d.last_7_days} />
              <Card title="Last 30 days" s={d.last_30_days} />
              <Card title="All time" s={d.all_time} />
            </div>
            <h2 className="mt-10 text-lg font-semibold">Latest trades</h2>
            <div className="mt-3 overflow-x-auto rounded-xl border border-[var(--border)]">
              <table className="w-full text-sm">
                <thead className="text-left text-[var(--muted)]">
                  <tr>
                    <th className="px-4 py-2">Opened (UTC)</th>
                    <th className="px-4 py-2">Side</th>
                    <th className="px-4 py-2 text-right">Result (R)</th>
                    <th className="px-4 py-2 text-right">Outcome</th>
                  </tr>
                </thead>
                <tbody>
                  {(d.recent ?? []).map((t) => (
                    <tr key={t.opened_at + t.side} className="border-t border-[var(--border)]">
                      <td className="px-4 py-2 tabular-nums">
                        {t.opened_at.replace("T", " ").slice(0, 16)}
                      </td>
                      <td className="px-4 py-2">{t.side}</td>
                      <td className="px-4 py-2 text-right tabular-nums">{dash(t.result_r)}</td>
                      <td className="px-4 py-2 text-right capitalize">{t.outcome}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-6 text-xs text-[var(--muted)]">
              {d.disclosure} Trading gold involves a high risk of loss. See our{" "}
              <a className="underline" href="/risk-disclosure">
                risk disclosure
              </a>
              .
            </p>
          </>
        ) : null}
      </main>
      <PricingFooter />
    </div>
  );
}
