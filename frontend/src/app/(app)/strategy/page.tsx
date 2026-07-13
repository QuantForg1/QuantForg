"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { Copy, Play, Trash2 } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { strategyApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, str } from "@/lib/desk";
import { Sparkles } from "lucide-react";

type RuleFlags = {
  liquidity_sweep_bullish: boolean;
  liquidity_sweep_bearish: boolean;
  order_block_bullish: boolean;
  order_block_bearish: boolean;
  fvg_bullish: boolean;
  fvg_bearish: boolean;
  has_structure: boolean;
  has_liquidity: boolean;
  has_order_blocks: boolean;
  has_fvgs: boolean;
};

const defaultRules: RuleFlags = {
  liquidity_sweep_bullish: false,
  liquidity_sweep_bearish: false,
  order_block_bullish: false,
  order_block_bearish: false,
  fvg_bullish: false,
  fvg_bearish: false,
  has_structure: true,
  has_liquidity: true,
  has_order_blocks: true,
  has_fvgs: true,
};

export default function StrategyPage() {
  const qc = useQueryClient();
  const [symbol, setSymbol] = useState("EURUSD");
  const [timeframe, setTimeframe] = useState("m15");
  const [structureBias, setStructureBias] = useState("up");
  const [rules, setRules] = useState<RuleFlags>(defaultRules);
  const [lastResult, setLastResult] = useState<Record<string, unknown> | null>(null);

  const signalsQ = useQuery({
    queryKey: ["strategy-signals"],
    queryFn: strategyApi.signals,
    retry: false,
  });

  const evaluate = useMutation({
    mutationFn: strategyApi.evaluate,
    onSuccess: async (data) => {
      setLastResult(asRecord(data));
      toast.success(`Decision: ${str(asRecord(data).decision)}`);
      await qc.invalidateQueries({ queryKey: ["strategy-signals"] });
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Evaluate failed"),
  });

  const signals = asList(signalsQ.data).map(asRecord);

  const templates = useMemo(
    () => [
      { id: "ict-bull", name: "ICT Bullish Sweep", bias: "up", patch: { liquidity_sweep_bullish: true, order_block_bullish: true, fvg_bullish: true } },
      { id: "ict-bear", name: "ICT Bearish Sweep", bias: "down", patch: { liquidity_sweep_bearish: true, order_block_bearish: true, fvg_bearish: true } },
      { id: "range", name: "Range Watch", bias: "range", patch: { has_structure: true, has_liquidity: false } },
    ],
    [],
  );

  const runEvaluate = () => {
    evaluate.mutate({
      request_id: `ui-${Date.now()}`,
      symbol,
      timeframe,
      market_open: true,
      structure_bias: structureBias,
      ...rules,
      check_risk: true,
    });
  };

  const toggle = (key: keyof RuleFlags) =>
    setRules((r) => ({ ...r, [key]: !r[key] }));

  return (
    <div>
      <PageHeader
        title="Strategy Builder"
        description="Compose market-structure rules, evaluate signals, and review the library."
        actions={
          <>
            <Button size="sm" onClick={runEvaluate} disabled={evaluate.isPending}>
              <Play className="h-3.5 w-3.5" /> Backtest / Evaluate
            </Button>
            <Button
              size="sm"
              variant="secondary"
            onClick={() => {
              void (async () => {
                try {
                  await navigator.clipboard.writeText(
                    JSON.stringify({ symbol, timeframe, structureBias, rules }, null, 2),
                  );
                  toast.success("Strategy snapshot copied");
                } catch {
                  toast.error("Clipboard unavailable");
                }
              })();
            }}
            >
              <Copy className="h-3.5 w-3.5" /> Duplicate
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setRules(defaultRules);
                setLastResult(null);
                toast.message("Builder reset");
              }}
            >
              <Trash2 className="h-3.5 w-3.5" /> Delete
            </Button>
          </>
        }
      />

      <div className="grid gap-4 xl:grid-cols-[0.85fr_1.4fr_0.95fr]">
        <Card>
          <CardHeader>
            <CardTitle>Strategy Library</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {templates.map((t) => (
              <button
                key={t.id}
                type="button"
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2.5 text-left transition hover:border-[var(--accent)]/40"
                onClick={() => {
                  setStructureBias(t.bias);
                  setRules((r) => ({ ...r, ...t.patch }));
                }}
              >
                <p className="text-sm font-medium text-[var(--fg)]">{t.name}</p>
                <p className="text-xs text-[var(--fg-subtle)]">Bias · {t.bias}</p>
              </button>
            ))}
            <div className="border-t border-[var(--border)] pt-3">
              <p className="mb-2 text-xs uppercase tracking-wider text-[var(--fg-subtle)]">
                Recent signals
              </p>
              {signalsQ.isLoading ? (
                <DeskSkeleton rows={2} />
              ) : signalsQ.isError ? (
                <DeskError message="Signals unavailable." onRetry={() => signalsQ.refetch()} />
              ) : signals.length === 0 ? (
                <DeskEmpty
                  icon={Sparkles}
                  title="No signals yet"
                  description="Evaluate a strategy to populate the library."
                />
              ) : (
                <ul className="space-y-2">
                  {signals.slice(0, 8).map((s) => (
                    <li
                      key={str(s.id)}
                      className="rounded-md border border-[var(--border)] px-2.5 py-2 text-xs"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium">{str(s.symbol)}</span>
                        <Badge tone={s.rejected ? "danger" : "success"}>
                          {str(s.direction)}
                        </Badge>
                      </div>
                      <p className="mt-1 text-[var(--fg-subtle)]">
                        conf {(numish(s.confidence) * 100).toFixed(0)}% · {str(s.timeframe)}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Visual Rule Builder</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-2 sm:grid-cols-2">
              {(Object.keys(rules) as (keyof RuleFlags)[]).map((key) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => toggle(key)}
                  className={`rounded-lg border px-3 py-3 text-left text-sm transition ${
                    rules[key]
                      ? "border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--fg)]"
                      : "border-[var(--border)] bg-[var(--surface-2)] text-[var(--fg-muted)]"
                  }`}
                >
                  <span className="block font-medium">{key.replaceAll("_", " ")}</span>
                  <span className="text-xs opacity-70">{rules[key] ? "Armed" : "Off"}</span>
                </button>
              ))}
            </div>
            {lastResult ? (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="mt-4 rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)] p-3"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone="accent">{str(lastResult.decision)}</Badge>
                  <span className="text-xs text-[var(--fg-subtle)]">
                    {str(lastResult.symbol)} · {str(lastResult.timeframe)}
                  </span>
                </div>
                <ul className="mt-2 space-y-1 text-xs text-[var(--fg-muted)]">
                  {asList(lastResult.reasons)
                    .slice(0, 6)
                    .map((r, i) => (
                      <li key={i}>• {String(r)}</li>
                    ))}
                </ul>
              </motion.div>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Parameters</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="space-y-1.5">
              <Label>Symbol</Label>
              <Input value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} />
            </div>
            <div className="space-y-1.5">
              <Label>Timeframe</Label>
              <Input value={timeframe} onChange={(e) => setTimeframe(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Structure bias</Label>
              <Input value={structureBias} onChange={(e) => setStructureBias(e.target.value)} />
            </div>
            <Button className="w-full" onClick={runEvaluate} disabled={evaluate.isPending}>
              Save & Evaluate
            </Button>
            <p className="text-xs text-[var(--fg-subtle)]">
              Uses existing <code>/strategy/evaluate</code> — no mock responses.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function numish(v: unknown) {
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : 0;
}
