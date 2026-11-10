"use client";

import { useCallback, useEffect, useState } from "react";
import { multiAccountOpsApi } from "@/lib/api/endpoints";
import { asRecord } from "@/lib/desk";
import { MetricCard, OpsPanel, StatusPill } from "@/components/ops/auto-trading-ops-ui";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

type LoadState = "loading" | "ready" | "empty" | "unavailable" | "error";

function num(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number" && Number.isFinite(v)) return String(v);
  if (typeof v === "string" && v.trim()) return v;
  return "—";
}

function toneForCount(
  value: unknown,
  opts?: { warnAbove?: number; badAbove?: number },
): "ok" | "warn" | "bad" | "neutral" | "accent" {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return "neutral";
  if (opts?.badAbove !== undefined && n > opts.badAbove) return "bad";
  if (opts?.warnAbove !== undefined && n > opts.warnAbove) return "warn";
  if (n === 0) return "neutral";
  return "accent";
}

export function MultiAccountOpsWorkspace() {
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState<string>("");
  const [payload, setPayload] = useState<Record<string, unknown> | null>(null);
  const [updatedAt, setUpdatedAt] = useState<string>("");

  const refresh = useCallback(async () => {
    setState((prev) => (prev === "ready" ? "ready" : "loading"));
    setError("");
    try {
      const raw = await multiAccountOpsApi.ownerSummary();
      const data = asRecord(raw) ?? {};
      const cards = asRecord(data.cards) ?? {};
      const hasCards = Object.keys(cards).length > 0;
      setPayload(data);
      setUpdatedAt(
        typeof data.generated_at === "string"
          ? data.generated_at
          : new Date().toISOString(),
      );
      setState(hasCards ? "ready" : "empty");
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Unable to load multi-account ops";
      // Owner gate / network → unavailable vs hard error
      if (/403|401|designated_owner|forbidden/i.test(message)) {
        setState("unavailable");
        setError("Owner authorization required for global multi-account ops.");
      } else {
        setState("error");
        setError(message);
      }
      setPayload(null);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const id = window.setInterval(() => {
      void refresh();
    }, 30_000);
    return () => window.clearInterval(id);
  }, [refresh]);

  const cards = asRecord(payload?.cards) ?? {};
  const flags = asRecord(payload?.feature_flags) ?? {};
  const safety = asRecord(payload?.safety) ?? {};
  const workers = asRecord(cards.workers) ?? {};
  const latency = asRecord(cards.delivery_latency) ?? {};
  const retries = asRecord(cards.retry_counts) ?? {};
  const byLifecycle = asRecord(cards.by_lifecycle_state) ?? {};
  const brokers = Array.isArray(cards.brokers) ? cards.brokers : [];

  return (
    <div className="space-y-[var(--space-4)]">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="accent">Observe only</Badge>
          <StatusPill
            label={
              flags.MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED === true
                ? "LIVE submit ON"
                : "LIVE submit OFF"
            }
            ok={flags.MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED !== true}
            warn={flags.MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED === true}
          />
          <StatusPill
            label={
              flags.MULTI_ACCOUNT_DISPATCH_ENABLED === true
                ? "Dispatch flag ON"
                : "Dispatch flag OFF"
            }
            ok={flags.MULTI_ACCOUNT_DISPATCH_ENABLED !== true}
            warn={flags.MULTI_ACCOUNT_DISPATCH_ENABLED === true}
          />
          {updatedAt ? (
            <span className="font-mono text-[10px] text-[var(--fg-subtle)]">
              {updatedAt}
            </span>
          ) : null}
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={() => void refresh()}
          disabled={state === "loading"}
        >
          Refresh
        </Button>
      </div>

      {state === "loading" && !payload ? (
        <OpsPanel title="Multi-account queue">
          <p className="text-sm text-[var(--fg-muted)]">Loading live metrics…</p>
        </OpsPanel>
      ) : null}

      {state === "unavailable" || state === "error" ? (
        <OpsPanel title="Multi-account queue">
          <p className="text-sm text-[var(--danger)]">{error || "Unavailable"}</p>
          <p className="mt-2 text-xs text-[var(--fg-subtle)]">
            Refresh never enqueues jobs. LIVE multi-account submit stays disabled.
          </p>
        </OpsPanel>
      ) : null}

      {state === "empty" ? (
        <OpsPanel title="Multi-account queue">
          <p className="text-sm text-[var(--fg-muted)]">
            No queue metrics yet. Dispatch remains dry-run / flag-off until Owner
            authorization.
          </p>
        </OpsPanel>
      ) : null}

      {(state === "ready" || (payload && state === "loading")) && (
        <>
          <OpsPanel title="Dispatch queue">
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
              <MetricCard
                label="Queue depth"
                value={num(cards.queue_depth)}
                tone={toneForCount(cards.queue_depth, {
                  warnAbove: 20,
                  badAbove: 100,
                })}
              />
              <MetricCard
                label="Pending"
                value={num(cards.pending)}
                tone={toneForCount(cards.pending, { warnAbove: 20 })}
              />
              <MetricCard label="Claimed" value={num(cards.claimed)} tone="accent" />
              <MetricCard
                label="Delivered"
                value={num(cards.delivered)}
                tone="ok"
              />
              <MetricCard
                label="Acknowledged"
                value={num(cards.acknowledged)}
                tone="ok"
              />
              <MetricCard
                label="Failed"
                value={num(cards.failed)}
                tone={toneForCount(cards.failed, { warnAbove: 0, badAbove: 5 })}
              />
              <MetricCard
                label="Expired"
                value={num(cards.expired)}
                tone={toneForCount(cards.expired, { warnAbove: 0 })}
              />
              <MetricCard
                label="Dead letter"
                value={num(cards.dead_letter)}
                tone={toneForCount(cards.dead_letter, {
                  warnAbove: 0,
                  badAbove: 0,
                })}
              />
            </div>
          </OpsPanel>

          <div className="grid gap-4 lg:grid-cols-2">
            <OpsPanel title="Lifecycle states">
              {Object.keys(byLifecycle).length === 0 ? (
                <p className="text-sm text-[var(--fg-muted)]">No execution states yet.</p>
              ) : (
                <div className="grid grid-cols-2 gap-2">
                  {Object.entries(byLifecycle).map(([k, v]) => (
                    <MetricCard key={k} label={k} value={num(v)} />
                  ))}
                </div>
              )}
            </OpsPanel>

            <OpsPanel title="Workers">
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                <MetricCard label="Active" value={num(workers.active)} tone="accent" />
                <MetricCard label="Healthy" value={num(workers.healthy)} tone="ok" />
                <MetricCard
                  label="Stale"
                  value={num(workers.stale)}
                  tone={toneForCount(workers.stale, {
                    warnAbove: 0,
                    badAbove: 0,
                  })}
                />
                <MetricCard label="Total" value={num(workers.total)} />
                <MetricCard
                  label="Heartbeat age (s)"
                  value={num(workers.oldest_heartbeat_age_sec)}
                  tone={toneForCount(workers.oldest_heartbeat_age_sec, {
                    warnAbove: 60,
                    badAbove: 180,
                  })}
                />
                <MetricCard
                  label="In-process"
                  value={num(workers.in_process_count)}
                  tone="neutral"
                />
              </div>
            </OpsPanel>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <OpsPanel title="Delivery latency & retries">
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                <MetricCard
                  label="Samples"
                  value={num(latency.sample_count)}
                  tone="neutral"
                />
                <MetricCard label="p50 ms" value={num(latency.p50_ms)} />
                <MetricCard label="p95 ms" value={num(latency.p95_ms)} />
                <MetricCard label="Max ms" value={num(latency.max_ms)} />
                <MetricCard
                  label="Retry events"
                  value={num(retries.retry_events)}
                  tone={toneForCount(retries.retry_events, { warnAbove: 0 })}
                />
                <MetricCard
                  label="Max attempts"
                  value={num(retries.max_attempt_count)}
                />
              </div>
            </OpsPanel>

            <OpsPanel title="Per-broker operational status">
              {brokers.length === 0 ? (
                <p className="text-sm text-[var(--fg-muted)]">
                  No broker account aggregates available.
                </p>
              ) : (
                <div className="max-h-56 space-y-1 overflow-auto">
                  {brokers.map((row, idx) => {
                    const r = asRecord(row) ?? {};
                    const label = `${num(r.broker)} · ${num(r.platform)} · ${num(r.environment)} · ${num(r.status)}`;
                    return (
                      <div
                        key={`${label}-${idx}`}
                        className="flex items-center justify-between gap-2 border-b border-[var(--border)]/50 py-1.5 text-[12px] last:border-0"
                      >
                        <span className="truncate text-[var(--fg-muted)]">{label}</span>
                        <span className="font-mono tabular text-[var(--fg)]">
                          {num(r.n)}
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
            </OpsPanel>
          </div>

          <p className="text-[11px] text-[var(--fg-subtle)]">
            Safety: live_submit_allowed=
            {String(safety.live_submit_allowed ?? false)} · refresh_does_not_enqueue=
            {String(safety.refresh_does_not_enqueue ?? true)} · Weltrade singleton is
            not shared across multi-account workers.
          </p>
        </>
      )}
    </div>
  );
}
