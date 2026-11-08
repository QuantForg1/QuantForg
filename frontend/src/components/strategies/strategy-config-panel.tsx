"use client";

import { Play } from "lucide-react";
import { motion } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  isFlatPrimitiveParams,
  mergedParamsFromJson,
  serializeParams,
} from "@/components/strategies/strategy-utils";
import { asList, asRecord, str } from "@/lib/desk";

export type ConfigTab = "parameters" | "logic" | "entry" | "filters" | "risk";

const TAB_LABELS: { id: ConfigTab; label: string }[] = [
  { id: "parameters", label: "Parameters" },
  { id: "logic", label: "Logic & Rules" },
  { id: "entry", label: "Entry & Exit" },
  { id: "filters", label: "Filters" },
  { id: "risk", label: "Risk Integration" },
];

type StrategyConfigPanelProps = {
  title: string;
  subtitle: string;
  configTab: ConfigTab;
  onConfigTab: (tab: ConfigTab) => void;
  strategyKey: string;
  paramsJson: string;
  customRulesJson: string;
  onParamsJson: (v: string) => void;
  onCustomRulesJson: (v: string) => void;
  defaultParams: Record<string, unknown> | undefined;
  symbol: string;
  timeframe: string;
  maxTrades: string;
  dailyLoss: string;
  maxExposure: string;
  onReset: () => void;
  onSave: () => void;
  savePending: boolean;
  onValidate: () => void;
  onRun: () => void;
  runPending: boolean;
  lastResult: Record<string, unknown> | null;
};

function numish(v: unknown) {
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : 0;
}

export function StrategyConfigPanel({
  title,
  subtitle,
  configTab,
  onConfigTab,
  strategyKey,
  paramsJson,
  customRulesJson,
  onParamsJson,
  onCustomRulesJson,
  defaultParams,
  symbol,
  timeframe,
  maxTrades,
  dailyLoss,
  maxExposure,
  onReset,
  onSave,
  savePending,
  onValidate,
  onRun,
  runPending,
  lastResult,
}: StrategyConfigPanelProps) {
  const signalBlock = lastResult ? asRecord(lastResult.signal) : null;
  const explanations = signalBlock
    ? asList(signalBlock.explanations).map(asRecord)
    : [];

  const merged = mergedParamsFromJson(paramsJson, defaultParams);
  const useFlatForm =
    strategyKey !== "custom_rules" && isFlatPrimitiveParams(merged);

  const patchParam = (key: string, raw: string) => {
    const next = { ...merged };
    const prev = merged[key];
    if (typeof prev === "number") {
      const n = Number(raw);
      next[key] = Number.isFinite(n) ? n : raw;
    } else if (typeof prev === "boolean") {
      next[key] = raw === "true";
    } else {
      next[key] = raw;
    }
    onParamsJson(serializeParams(next));
  };

  return (
    <Card>
      <CardHeader className="flex-row flex-wrap items-center justify-between gap-3">
        <div>
          <CardTitle>{title}</CardTitle>
          <p className="mt-1 text-xs text-[var(--fg-muted)]">{subtitle}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge tone="success">Active</Badge>
          <Button size="sm" variant="ghost" onClick={onReset}>
            Reset
          </Button>
          <Button
            className="qf-btn-hot border-0"
            size="sm"
            onClick={onSave}
            disabled={savePending}
          >
            Save Changes
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div
          className="flex flex-wrap gap-1 border-b border-[var(--border)] pb-2"
          role="tablist"
          aria-label="Strategy configuration"
        >
          {TAB_LABELS.map(({ id, label }) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={configTab === id}
              onClick={() => onConfigTab(id)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                configTab === id
                  ? "bg-[var(--cta-soft)] text-[var(--cta)]"
                  : "text-[var(--fg-muted)] hover:bg-[var(--surface-2)] hover:text-[var(--fg)]"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {configTab === "parameters" ? (
          useFlatForm ? (
            <div className="grid gap-3 sm:grid-cols-2">
              {Object.entries(merged).map(([key, val]) => (
                <div key={key} className="space-y-1.5">
                  <Label htmlFor={`param-${key}`} className="capitalize">
                    {key.replaceAll("_", " ")}
                  </Label>
                  {typeof val === "boolean" ? (
                    <select
                      id={`param-${key}`}
                      className="h-9 w-full rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface-2)] px-2 text-sm"
                      value={String(val)}
                      onChange={(e) => patchParam(key, e.target.value)}
                    >
                      <option value="true">true</option>
                      <option value="false">false</option>
                    </select>
                  ) : (
                    <Input
                      id={`param-${key}`}
                      value={String(val ?? "")}
                      onChange={(e) => patchParam(key, e.target.value)}
                    />
                  )}
                </div>
              ))}
            </div>
          ) : (
            <textarea
              className="min-h-[220px] w-full rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface-2)] p-3 font-mono text-xs text-[var(--fg)]"
              value={strategyKey === "custom_rules" ? customRulesJson : paramsJson}
              onChange={(e) =>
                strategyKey === "custom_rules"
                  ? onCustomRulesJson(e.target.value)
                  : onParamsJson(e.target.value)
              }
              aria-label="Strategy parameters JSON"
            />
          )
        ) : (
          <div className="min-h-[220px] rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--bg)]/35 p-4 text-sm text-[var(--fg-muted)]">
            {configTab === "logic" ? (
              <p>
                Logic follows the selected catalog plugin and any custom rules JSON.
                Orders still require risk and OMS approval.
              </p>
            ) : null}
            {configTab === "entry" ? (
              <p>
                Entry and exit levels come from live evaluate / MT5 bars — never sample
                prices. Run Evaluate to refresh.
              </p>
            ) : null}
            {configTab === "filters" ? (
              <p>
                Symbol {symbol} · timeframe {timeframe}. Filters stay advisory until the
                risk engine confirms.
              </p>
            ) : null}
            {configTab === "risk" ? (
              <ul className="space-y-2">
                <li>Max trades: {maxTrades}</li>
                <li>Daily loss %: {dailyLoss}</li>
                <li>Max exposure %: {maxExposure}</li>
                <li>Live path requires EXECUTION_ENABLED and owned broker session.</li>
              </ul>
            ) : null}
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="secondary" onClick={onValidate}>
            Validate
          </Button>
          <Button size="sm" onClick={onRun} disabled={runPending}>
            <Play className="h-3.5 w-3.5" /> Run (MT5 bars)
          </Button>
        </div>

        {signalBlock ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--bg-elevated)] p-3"
          >
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="accent">{str(signalBlock.action)}</Badge>
              <span className="text-xs text-[var(--fg-subtle)]">
                conf {(numish(signalBlock.confidence) * 100).toFixed(0)}%
              </span>
            </div>
            <p className="mt-2 text-xs uppercase tracking-wider text-[var(--fg-subtle)]">
              Explainability
            </p>
            <ul className="mt-1 space-y-2 text-xs text-[var(--fg-muted)]">
              {explanations.length === 0 ? (
                asList(signalBlock.reasons).map((r, i) => (
                  <li key={i}>• {String(r)}</li>
                ))
              ) : (
                explanations.map((e, i) => (
                  <li key={i} className="rounded-md border border-[var(--border)] p-2">
                    <p className="font-medium text-[var(--fg)]">{str(e.reason)}</p>
                    <p>
                      {str(e.indicator)} · threshold {str(e.threshold)}
                      {e.value ? ` · value ${str(e.value)}` : ""}
                    </p>
                    <p className="text-[var(--fg-subtle)]">{str(e.market_context)}</p>
                  </li>
                ))
              )}
            </ul>
            {lastResult?.risk ? (
              <p className="mt-2 text-xs text-[var(--fg-subtle)]">
                Risk: {asRecord(lastResult.risk).allowed ? "allowed" : "blocked"} ·{" "}
                {asList(asRecord(lastResult.risk).reasons)
                  .slice(0, 2)
                  .map(String)
                  .join("; ")}
              </p>
            ) : null}
          </motion.div>
        ) : null}
      </CardContent>
    </Card>
  );
}
