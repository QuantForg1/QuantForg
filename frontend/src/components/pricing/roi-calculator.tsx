"use client";

import { useMemo, useState } from "react";

const LICENSE = 2499;
const PROFIT_STEPS = [500, 1000, 2000, 5000, 10000] as const;
const HORIZONS = [6, 12, 24] as const;

function formatUsd(n: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(n);
}

export function RoiCalculator() {
  const [profitIdx, setProfitIdx] = useState(2);
  const [horizonIdx, setHorizonIdx] = useState(1);
  const monthly = PROFIT_STEPS[profitIdx] ?? 2000;
  const months = HORIZONS[horizonIdx] ?? 12;

  const { paybackMonths, returnMultiple, horizonProfit, horizonNet } = useMemo(() => {
    const payback = LICENSE / monthly;
    const profit = monthly * months;
    const multiple = profit / LICENSE;
    return {
      paybackMonths: payback,
      returnMultiple: multiple,
      horizonProfit: profit,
      horizonNet: profit - LICENSE,
    };
  }, [monthly, months]);

  const paybackLabel =
    paybackMonths < 1
      ? "< 1 month"
      : paybackMonths < 12
        ? `${paybackMonths.toFixed(1)} months`
        : `${(paybackMonths / 12).toFixed(1)} years`;

  return (
    <div className="qf-glass-card relative overflow-hidden p-6 sm:p-8">
      <div
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,rgba(0,212,224,0.1),transparent_55%)]"
        aria-hidden
      />
      <div className="relative">
        <p className="qf-label text-[var(--accent)]">ROI calculator</p>
        <h3 className="mt-2 font-[family-name:var(--font-display)] text-xl tracking-tight sm:text-2xl">
          Illustrative return on the lifetime license
        </h3>
        <p className="mt-2 max-w-2xl text-sm text-[var(--fg-muted)]">
          Values are illustrative estimates based on your assumed monthly trading profit — not
          guarantees, forecasts, or audited performance.
        </p>

        <div className="mt-8 grid gap-8 lg:grid-cols-2">
          <div>
            <label className="block" htmlFor="qf-roi-profit">
              <span className="text-sm font-medium text-[var(--fg)]">Monthly trading profit</span>
              <span className="mt-1 block font-[family-name:var(--font-display)] text-3xl font-semibold tracking-tight text-[var(--accent)]">
                {formatUsd(monthly)}
              </span>
            </label>
            <input
              id="qf-roi-profit"
              type="range"
              min={0}
              max={PROFIT_STEPS.length - 1}
              step={1}
              value={profitIdx}
              onChange={(e) => setProfitIdx(Number(e.target.value))}
              className="qf-roi-slider mt-5 w-full"
              aria-valuetext={`${formatUsd(monthly)} per month`}
            />
            <div className="mt-2 flex justify-between text-[10px] uppercase tracking-wider text-[var(--fg-subtle)] sm:text-xs">
              {PROFIT_STEPS.map((s, i) => (
                <button
                  key={s}
                  type="button"
                  className={`transition-colors hover:text-[var(--fg)] ${
                    profitIdx === i ? "text-[var(--accent)]" : ""
                  }`}
                  onClick={() => setProfitIdx(i)}
                >
                  {formatUsd(s)}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block" htmlFor="qf-roi-horizon">
              <span className="text-sm font-medium text-[var(--fg)]">Horizon</span>
              <span className="mt-1 block font-[family-name:var(--font-display)] text-3xl font-semibold tracking-tight text-[var(--fg)]">
                {months} months
              </span>
            </label>
            <input
              id="qf-roi-horizon"
              type="range"
              min={0}
              max={HORIZONS.length - 1}
              step={1}
              value={horizonIdx}
              onChange={(e) => setHorizonIdx(Number(e.target.value))}
              className="qf-roi-slider mt-5 w-full"
              aria-valuetext={`${months} months`}
            />
            <div className="mt-2 flex justify-between text-[10px] uppercase tracking-wider text-[var(--fg-subtle)] sm:text-xs">
              {HORIZONS.map((h, i) => (
                <button
                  key={h}
                  type="button"
                  className={`transition-colors hover:text-[var(--fg)] ${
                    horizonIdx === i ? "text-[var(--accent)]" : ""
                  }`}
                  onClick={() => setHorizonIdx(i)}
                >
                  {h} Months
                </button>
              ))}
            </div>
          </div>
        </div>

        <dl className="mt-8 grid gap-3 sm:grid-cols-3">
          <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-elevated)]/70 p-4">
            <dt className="text-xs uppercase tracking-wider text-[var(--fg-subtle)]">
              Estimated payback
            </dt>
            <dd className="mt-1 font-[family-name:var(--font-display)] text-2xl font-semibold tracking-tight text-[var(--accent)]">
              {paybackLabel}
            </dd>
            <p className="mt-1 text-xs text-[var(--fg-muted)]">Software cost {formatUsd(LICENSE)}</p>
          </div>
          <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-elevated)]/70 p-4">
            <dt className="text-xs uppercase tracking-wider text-[var(--fg-subtle)]">
              Estimated return multiple
            </dt>
            <dd className="mt-1 font-[family-name:var(--font-display)] text-2xl font-semibold tracking-tight">
              {returnMultiple.toFixed(1)}×
            </dd>
            <p className="mt-1 text-xs text-[var(--fg-muted)]">
              Over {months} months at selected profit
            </p>
          </div>
          <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-elevated)]/70 p-4">
            <dt className="text-xs uppercase tracking-wider text-[var(--fg-subtle)]">
              Horizon net (illustrative)
            </dt>
            <dd className="mt-1 font-[family-name:var(--font-display)] text-2xl font-semibold tracking-tight">
              {formatUsd(horizonNet)}
            </dd>
            <p className="mt-1 text-xs text-[var(--fg-muted)]">
              {formatUsd(horizonProfit)} profit − license
            </p>
          </div>
        </dl>
      </div>
    </div>
  );
}
