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

function InfoCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <p className="text-[11px] uppercase tracking-wide text-[var(--fg-subtle)]">{label}</p>
      <p className="mt-1 truncate text-sm font-medium text-[var(--fg)]">{value}</p>
    </div>
  );
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
  const parameterRows = Object.entries(merged);
  const fieldClass =
    "h-11 w-full rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--bg-elevated)] px-3 text-base text-[var(--fg)] sm:h-10 sm:text-sm";

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
          <Badge tone="neutral">Selected</Badge>
          <Button size="sm" variant="ghost" onClick={onReset}>
            Reset
          </Button>
          <Button
            className="qf-btn-hot border-0"
            size="sm"
            onClick={onSave}
            disabled={savePending}
          >
            {savePending ? "Running…" : "Save & Run"}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div
          className="-mx-1 flex gap-1 overflow-x-auto border-b border-[var(--border)] px-1"
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
              className={`h-10 shrink-0 border-b-2 px-3 text-xs font-medium transition-colors ${
                configTab === id
                  ? "border-[var(--accent)] text-[var(--fg)]"
                  : "border-transparent text-[var(--fg-muted)] hover:text-[var(--fg)]"
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
                      className={fieldClass}
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
        ) : configTab === "logic" ? (
          parameterRows.length === 0 ? (
            <p className="text-sm leading-relaxed text-[var(--fg-muted)]">
              The catalogue did not return parameters for this strategy.
            </p>
          ) : (
            <ul className="divide-y divide-[var(--border)] rounded-[var(--radius-os)] border border-[var(--border)]">
              {parameterRows.map(([key, value]) => (
                <li key={key} className="flex items-center justify-between gap-3 px-3 py-2.5 text-sm">
                  <span className="text-[var(--fg-muted)]">{key.replaceAll("_", " ")}</span>
                  <span className="truncate font-medium tabular text-[var(--fg)]">{String(value)}</span>
                </li>
              ))}
            </ul>
          )
        ) : configTab === "entry" ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <InfoCell label="Last action" value={signalBlock ? str(signalBlock.action) : "No evaluate result yet"} />
            <InfoCell
              label="Confidence"
              value={
                signalBlock && Number.isFinite(Number(signalBlock.confidence))
                  ? `${(Number(signalBlock.confidence) * 100).toFixed(0)}%`
                  : "Not returned"
              }
            />
            <p className="text-xs leading-relaxed text-[var(--fg-muted)] sm:col-span-2">
              Entry and exit levels come from the latest evaluate on MT5 bars. Validate checks the current parameters without sending an order.
            </p>
          </div>
        ) : configTab === "filters" ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <InfoCell label="Symbol" value={symbol || "—"} />
            <InfoCell label="Timeframe" value={timeframe || "—"} />
            <p className="text-xs leading-relaxed text-[var(--fg-muted)] sm:col-span-2">
              Symbol and timeframe are edited in Strategy Information. They stay advisory until the risk engine confirms.
            </p>
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-3">
            <InfoCell label="Max trades" value={maxTrades || "—"} />
            <InfoCell label="Daily loss" value={dailyLoss ? `${dailyLoss}%` : "—"} />
            <InfoCell label="Max exposure" value={maxExposure ? `${maxExposure}%` : "—"} />
            <p className="text-xs leading-relaxed text-[var(--fg-muted)] sm:col-span-3">
              These limits are the current desk values. Live execution still requires the risk engine, OMS gates, and an owned broker session.
            </p>
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
              {Number.isFinite(Number(signalBlock.confidence)) ? (
                <span className="text-xs text-[var(--fg-subtle)]">
                  conf {(Number(signalBlock.confidence) * 100).toFixed(0)}%
                </span>
              ) : null}
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
