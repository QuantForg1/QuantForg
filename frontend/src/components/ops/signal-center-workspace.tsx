"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, X } from "lucide-react";
import { PageMotion } from "@/components/desk/motion";
import { MetricBar } from "@/components/ops/noc/noc-primitives";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { signalCenterApi } from "@/lib/api/endpoints";
import {
  formatSignalHeadline,
  signalDirectionGlyph,
} from "@/lib/ops/signal-display";
import { displayTradingSymbol } from "@/lib/trading/gold-only";
import { cn } from "@/lib/utils";

type SignalRow = {
  symbol: string;
  direction: string;
  badge: string;
  current_price: unknown;
  confidence: number;
  quality: number;
  momentum: number;
  structure: number;
  trend: string;
  atr: unknown;
  spread: unknown;
  liquidity: unknown;
  risk: unknown;
  rr: unknown;
  expected_hold: unknown;
  time_generated: string;
  session: string;
  strategy: string;
  probability: number;
  reasoning: string | null;
  ai_explanation: string | null;
  asset_class?: string;
  detail?: Record<string, unknown>;
};

const DIR_FILTERS = ["ALL", "BUY", "SELL", "WAIT", "NO_TRADE"] as const;
const CLASS_FILTERS = ["all", "forex", "crypto", "metals", "indices", "energy"] as const;

function asSignals(payload: Record<string, unknown> | undefined): SignalRow[] {
  const items = payload?.items;
  if (!Array.isArray(items)) return [];
  return items
    .filter((x): x is Record<string, unknown> => !!x && typeof x === "object")
    .map((x) => ({
      symbol: String(x.symbol ?? ""),
      direction: String(x.direction ?? "NONE"),
      badge: String(x.badge ?? "No Trade"),
      current_price: x.current_price,
      confidence: Number(x.confidence ?? 0),
      quality: Number(x.quality ?? 0),
      momentum: Number(x.momentum ?? 0),
      structure: Number(x.structure ?? 0),
      trend: String(x.trend ?? "—"),
      atr: x.atr,
      spread: x.spread,
      liquidity: x.liquidity,
      risk: x.risk,
      rr: x.rr,
      expected_hold: x.expected_hold,
      time_generated: String(x.time_generated ?? "—"),
      session: String(x.session ?? "—"),
      strategy: String(x.strategy ?? "—"),
      probability: Number(x.probability ?? 0),
      reasoning: x.reasoning == null ? null : String(x.reasoning),
      ai_explanation:
        x.ai_explanation == null ? null : String(x.ai_explanation),
      asset_class: x.asset_class == null ? undefined : String(x.asset_class),
      detail:
        x.detail && typeof x.detail === "object"
          ? (x.detail as Record<string, unknown>)
          : undefined,
    }))
    .filter((r) => r.symbol);
}

function badgeTone(
  badge: string,
): "success" | "danger" | "warning" | "neutral" | "accent" {
  const b = badge.toUpperCase();
  if (b.includes("BUY")) return "success";
  if (b.includes("SELL")) return "danger";
  if (b === "WAIT") return "warning";
  return "neutral";
}

function fmt(v: unknown): string {
  if (v == null || v === "") return "—";
  return String(v);
}

export function SignalCenterWorkspace() {
  const [q, setQ] = useState("");
  const [direction, setDirection] = useState<(typeof DIR_FILTERS)[number]>("ALL");
  const [assetClass, setAssetClass] =
    useState<(typeof CLASS_FILTERS)[number]>("all");
  const [strongOnly, setStrongOnly] = useState(false);
  const [highConf, setHighConf] = useState(false);
  const [selected, setSelected] = useState<SignalRow | null>(null);

  const query = useQuery({
    queryKey: [
      "signal-center",
      q,
      direction,
      assetClass,
      strongOnly,
      highConf,
    ],
    queryFn: () =>
      signalCenterApi.list({
        q: q || undefined,
        direction: direction === "ALL" ? undefined : direction,
        asset_class: assetClass === "all" ? undefined : assetClass,
        strong_only: strongOnly,
        high_confidence: highConf,
      }),
    refetchInterval: 15_000,
  });

  const signals = useMemo(() => asSignals(query.data), [query.data]);
  const dash = (query.data?.dashboard ?? {}) as Record<string, unknown>;

  return (
    <PageMotion>
      <div className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-8">
          {(
            [
              ["Total", dash.total_symbols],
              ["Enabled", dash.enabled_symbols],
              ["BUY", dash.buy_signals],
              ["SELL", dash.sell_signals],
              ["WAIT", dash.wait],
              ["No Trade", dash.no_trade],
              ["Avg Conf", dash.average_confidence],
              ["Avg Qual", dash.average_quality],
            ] as Array<[string, unknown]>
          ).map(([label, value]) => (
            <div
              key={label}
              className="border border-[var(--border)] bg-[var(--surface)] px-3 py-3"
            >
              <p className="text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                {label}
              </p>
              <p className="mt-1 font-mono text-xl text-[var(--fg)]">
                {value == null || value === "" ? "—" : String(value)}
              </p>
            </div>
          ))}
        </div>

        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="relative max-w-md flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--fg-subtle)]" />
            <Input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search symbol…"
              className="pl-9"
              aria-label="Search signals"
            />
          </div>
          <div className="flex flex-wrap gap-2">
            {DIR_FILTERS.map((d) => (
              <Button
                key={d}
                size="sm"
                variant={direction === d ? "default" : "outline"}
                onClick={() => setDirection(d)}
              >
                {d.replace("_", " ")}
              </Button>
            ))}
            {CLASS_FILTERS.map((c) => (
              <Button
                key={c}
                size="sm"
                variant={assetClass === c ? "secondary" : "outline"}
                onClick={() => setAssetClass(c)}
              >
                {c}
              </Button>
            ))}
            <Button
              size="sm"
              variant={strongOnly ? "default" : "outline"}
              onClick={() => setStrongOnly((v) => !v)}
            >
              Strong only
            </Button>
            <Button
              size="sm"
              variant={highConf ? "default" : "outline"}
              onClick={() => setHighConf((v) => !v)}
            >
              High confidence
            </Button>
          </div>
        </div>

        <p className="text-[11px] text-[var(--fg-subtle)]">
          LIVE scan · fabricated={String(query.data?.fabricated ?? false)} ·
          auto-refresh 15s · as_of {String(query.data?.as_of ?? "—")}
        </p>

        {query.isLoading ? (
          <p className="text-[var(--fg-muted)]">Loading LIVE signals…</p>
        ) : signals.length === 0 ? (
          <div className="border border-[var(--border)] bg-[var(--surface)] px-6 py-12 text-center text-[var(--fg-muted)]">
            No LIVE signals in the current scan window. Signals appear when the
            XAUUSD (Gold) scanner publishes scores — never simulated.
          </div>
        ) : (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {signals.map((s) => {
              const glyph = signalDirectionGlyph(s.direction);
              const buyish = glyph === "BUY";
              const sellish = glyph === "SELL";
              const waitish = glyph === "WAIT";
              const headline = formatSignalHeadline(s.direction, s.reasoning);
              return (
                <button
                  key={s.symbol}
                  type="button"
                  onClick={() => setSelected(s)}
                  className={cn(
                    "border border-[var(--border)] bg-[var(--surface)] p-4 text-left transition-colors duration-[var(--duration-os)] hover:border-[var(--accent)]/50",
                    buyish && "border-l-2 border-l-[var(--success)]",
                    sellish && "border-l-2 border-l-[var(--danger)]",
                    waitish && "border-l-2 border-l-[var(--warning)]",
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="font-mono text-lg font-semibold text-[var(--fg)]">
                        {displayTradingSymbol(s.symbol)}
                      </p>
                      <p className="mt-0.5 text-[11px] text-[var(--fg-subtle)]">
                        {s.strategy} · {s.session}
                      </p>
                    </div>
                    <Badge tone={badgeTone(s.badge)}>{s.badge}</Badge>
                  </div>
                  <div className="mt-3 flex items-center gap-3">
                    <span
                      className={cn(
                        "font-mono text-xs uppercase",
                        buyish && "text-[var(--success)]",
                        sellish && "text-[var(--danger)]",
                        waitish && "text-[var(--warning)]",
                        !buyish && !sellish && !waitish && "text-[var(--fg-muted)]",
                      )}
                      aria-hidden
                    >
                      {buyish ? "▲ BUY" : sellish ? "▼ SELL" : waitish ? "◆ WAIT" : "◆ NONE"}
                    </span>
                    <span className="font-mono text-sm text-[var(--fg)]">
                      {fmt(s.current_price)}
                    </span>
                    <span className="ml-auto font-mono text-xs text-[var(--accent)]">
                      {s.probability}%
                    </span>
                  </div>
                  <div className="mt-3 space-y-2">
                    <MetricBar label="Confidence" value={s.confidence} />
                    <MetricBar label="Quality" value={s.quality} />
                    <MetricBar label="Momentum" value={s.momentum} />
                  </div>
                  <div className="mt-3 grid grid-cols-3 gap-2 text-[10px] text-[var(--fg-muted)]">
                    <div>
                      Structure
                      <div className="font-mono text-[var(--fg)]">{s.structure}</div>
                    </div>
                    <div>
                      RR
                      <div className="font-mono text-[var(--fg)]">{fmt(s.rr)}</div>
                    </div>
                    <div>
                      Spread
                      <div className="font-mono text-[var(--fg)]">
                        {fmt(s.spread)}
                      </div>
                    </div>
                  </div>
                  {headline ? (
                    <p className="mt-3 line-clamp-2 text-[11px] text-[var(--fg-muted)]">
                      {headline}
                    </p>
                  ) : null}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {selected ? (
        <div
          className="fixed inset-0 z-50 flex justify-end bg-black/50"
          role="dialog"
          aria-modal="true"
          aria-label={`${selected.symbol} signal detail`}
          onClick={() => setSelected(null)}
          onKeyDown={(e) => {
            if (e.key === "Escape") setSelected(null);
          }}
        >
          <div
            className="h-full w-full max-w-lg overflow-y-auto border-l border-[var(--border)] bg-[var(--surface)] p-5 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="font-mono text-2xl font-semibold text-[var(--fg)]">
                  {displayTradingSymbol(selected.symbol)}
                </h2>
                <Badge tone={badgeTone(selected.badge)} className="mt-2">
                  {selected.badge}
                </Badge>
              </div>
              <Button
                size="sm"
                variant="ghost"
                aria-label="Close detail"
                onClick={() => setSelected(null)}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>

            <div className="mt-6 space-y-3">
              <MetricBar label="Confidence" value={selected.confidence} />
              <MetricBar label="Quality" value={selected.quality} />
              <MetricBar label="Momentum" value={selected.momentum} />
              <MetricBar label="Structure" value={selected.structure} />
            </div>

            <dl className="mt-6 grid grid-cols-2 gap-3 text-sm">
              {[
                ["Direction", selected.direction],
                ["Price", fmt(selected.current_price)],
                ["Trend", selected.trend],
                ["ATR", fmt(selected.atr)],
                ["Spread", fmt(selected.spread)],
                ["Liquidity", fmt(selected.liquidity)],
                ["Risk", fmt(selected.risk)],
                ["RR", fmt(selected.rr)],
                ["Hold", fmt(selected.expected_hold)],
                ["Strategy", selected.strategy],
                ["Session", selected.session],
                ["Generated", selected.time_generated],
              ].map(([k, v]) => (
                <div key={String(k)}>
                  <dt className="text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                    {k}
                  </dt>
                  <dd className="mt-0.5 font-mono text-[var(--fg)]">{v}</dd>
                </div>
              ))}
            </dl>

            <section className="mt-6">
              <h3 className="text-[11px] uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
                AI explanation
              </h3>
              <p className="mt-2 whitespace-pre-wrap text-sm text-[var(--fg-muted)]">
                {formatSignalHeadline(
                  selected.direction,
                  selected.ai_explanation || selected.reasoning,
                )}
              </p>
            </section>

            {selected.detail ? (
              <section className="mt-6 space-y-2">
                <h3 className="text-[11px] uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
                  Structure detail
                </h3>
                {(
                  [
                    ["BOS", selected.detail.bos],
                    ["CHOCH", selected.detail.choch],
                    ["Order Block", selected.detail.order_block],
                    ["FVG", selected.detail.fvg],
                    ["Why BUY", selected.detail.why_buy],
                    ["Why SELL", selected.detail.why_sell],
                    ["Why NO TRADE", selected.detail.why_no_trade],
                  ] as const
                ).map(([label, val]) => (
                  <div
                    key={label}
                    className="border-b border-[var(--border)]/60 py-2 text-sm"
                  >
                    <span className="text-[var(--fg-subtle)]">{label}</span>
                    <div className="mt-0.5 font-mono text-[var(--fg)]">
                      {fmt(val)}
                    </div>
                  </div>
                ))}
              </section>
            ) : null}
          </div>
        </div>
      ) : null}
    </PageMotion>
  );
}
