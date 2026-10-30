"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { LiveTradingControlPanel } from "@/components/ops/live-trading-control-panel";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiFetch } from "@/lib/api/client";
import {
  EXPERIMENT_DEFAULTS,
  EXPERIMENTAL_KEYS,
  POLICY_NUMERIC_KEYS,
  buildExperimentalChanges,
  buildPolicyChanges,
  m1ChoiceFromDocument,
  policyStateLines,
  policyStatusText,
  validateActiveDraft,
  validateExperimentalDraft,
  type M1Choice,
} from "@/lib/trading/admin-policy";

type PolicyPayload = {
  ok?: boolean;
  version?: number;
  source?: string;
  status?: string;
  error?: string;
  document?: Record<string, unknown> | null;
  applied_version?: number | null;
  worker_confirmed?: boolean;
  experimental?: Record<string, unknown> | null;
  experimental_promoted?: boolean;
  enforced_min_reward_risk?: string;
  commission?: Record<string, string> | null;
  pending_restart?: boolean;
};

type Overview = {
  owner?: { email?: string; role?: string; designated_owner?: boolean };
  deployment?: { commit_sha?: string };
  broker?: Record<string, unknown>;
  live_trading?: { state?: string };
  policy?: PolicyPayload;
  audit?: Array<Record<string, unknown>>;
};

const FIELD_LABELS: Record<(typeof POLICY_NUMERIC_KEYS)[number], string> = {
  max_planned_risk_pct: "Max planned risk % (ceiling 20)",
  daily_loss_pct: "Daily loss halt % (ceiling 48)",
  weekly_loss_pct: "Weekly loss halt % (0 = off until you set it)",
  max_drawdown_pct:
    "Overall drawdown halt % (0 = off until you set it, ceiling is the daily halt)",
  max_aggregate_open_risk_pct: "Max aggregate open risk % (ceiling 30, shared across positions)",
  max_concurrent_positions: "Max concurrent positions (1 to 5)",
  min_lot: "Min lot (empty uses the broker minimum, ceiling 0.01)",
  max_lot: "Max lot (ceiling 0.01)",
  max_spread: "Max spread (ceiling 1.00)",
  min_reward_risk:
    "Active minimum net reward:risk (at least 0.50). 0.10, 0.15, and 0.20 stay experimental.",
  min_trade_quality: "Minimum trade quality (70 to 100; default 70)",
  stop_atr_multiplier:
    "ATR stop multiplier (1.00, 1.25, or 1.50; default 1.00). 0.75 and 0.90 are rejected",
};

function text(value: unknown): string {
  if (value == null) return "—";
  return String(value);
}

export default function AdminControlPage() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [experimentalDraft, setExperimentalDraft] = useState<Record<string, string>>({});
  const [m1, setM1] = useState<M1Choice>("defer");
  const [m1Live, setM1Live] = useState<M1Choice>("defer");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    const body = await apiFetch<Overview>("/admin/control/overview");
    setOverview(body);
    const doc = body.policy?.document || {};
    const next: Record<string, string> = {};
    for (const key of POLICY_NUMERIC_KEYS) {
      const raw = doc[key];
      if (key === "min_reward_risk" && body.policy?.enforced_min_reward_risk) {
        next[key] = body.policy.enforced_min_reward_risk;
      } else if (key === "max_drawdown_pct" && (raw == null || raw === "")) {
        next[key] = "0";
      } else {
        next[key] = raw == null ? "" : String(raw);
      }
    }
    setDraft(next);
    const savedExperiment =
      doc.experimental && typeof doc.experimental === "object"
        ? (doc.experimental as Record<string, unknown>)
        : {};
    const experiment: Record<string, string> = { ...EXPERIMENT_DEFAULTS };
    for (const key of EXPERIMENTAL_KEYS) {
      const raw = savedExperiment[key];
      if (raw != null && String(raw) !== "") experiment[key] = String(raw);
    }
    setExperimentalDraft(experiment);
    setM1(m1ChoiceFromDocument(doc.m1_micro_enabled));
    setM1Live(m1ChoiceFromDocument(doc.m1_live_submit));
  }, []);

  useEffect(() => {
    let cancelled = false;
    load().catch((exc: unknown) => {
      if (!cancelled) {
        setError(exc instanceof Error ? exc.message : "Overview unavailable");
      }
    });
    return () => {
      cancelled = true;
    };
  }, [load]);

  async function savePolicy() {
    const version = overview?.policy?.version ?? 0;
    const confirmed = window.confirm(
      "Save this policy? It cannot raise risk above the approved ceilings, and it does not enable live trading.",
    );
    if (!confirmed) return;
    setSaving(true);
    setError("");
    setNotice("");
    const validation = validateActiveDraft(draft);
    if (validation.length) {
      setError(validation.join(" "));
      setSaving(false);
      return;
    }
    const changes = buildPolicyChanges({ draft, m1, m1Live });
    try {
      const saved = await apiFetch<PolicyPayload>("/admin/control/policy", {
        method: "PUT",
        body: {
          expected_version: version,
          reason: "admin control center save",
          changes,
        },
      });
      if (!saved.ok) {
        setError(saved.error || "Policy rejected");
      } else {
        setNotice(
          `Saved version ${saved.version}. Status ${saved.status || "saved"}. Applied version ${saved.applied_version ?? "pending"}.`,
        );
      }
      await load();
    } catch (exc: unknown) {
      setError(exc instanceof Error ? exc.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function saveExperimental(promote: boolean) {
    const version = overview?.policy?.version ?? 0;
    const validation = validateExperimentalDraft(experimentalDraft);
    if (validation.length) {
      setError(validation.join(" "));
      return;
    }
    const confirmed = window.confirm(
      promote
        ? "Promote this experiment into the saved production policy? It still is not loaded until the worker confirms the new version."
        : "Save this experiment only? It will not change the active production floor.",
    );
    if (!confirmed) return;
    setSaving(true);
    setError("");
    setNotice("");
    const changes = buildExperimentalChanges(experimentalDraft);
    if (promote) changes.promote_experimental = true;
    try {
      const saved = await apiFetch<PolicyPayload>("/admin/control/policy", {
        method: "PUT",
        body: {
          expected_version: version,
          reason: promote ? "promote experimental policy" : "save experimental policy",
          changes,
        },
      });
      if (!saved.ok) {
        setError(saved.error || "Experimental policy rejected");
      } else {
        setNotice(
          promote
            ? `Promoted into saved version ${saved.version}. Worker confirmed: ${saved.worker_confirmed ? "yes" : "not yet"}.`
            : `Experimental settings stored on version ${saved.version}. They are not the active floor.`,
        );
      }
      await load();
    } catch (exc: unknown) {
      setError(exc instanceof Error ? exc.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  const broker = overview?.broker || {};
  const policy = overview?.policy;
  const states = policy ? policyStateLines(policy) : null;
  const experimentLabels: Record<(typeof EXPERIMENTAL_KEYS)[number], string> = {
    max_planned_risk_pct: "Experimental planned risk % (ceiling 20)",
    max_aggregate_open_risk_pct: "Experimental aggregate open risk % (ceiling 30)",
    daily_loss_pct: "Experimental daily loss halt % (ceiling 48)",
    max_lot: "Experimental max lot (ceiling 0.01)",
    max_spread: "Experimental max spread (ceiling 1.00)",
    min_reward_risk: "Experimental reward:risk (0.10, 0.15, or 0.20)",
    min_trade_quality: "Experimental trade quality (70 to 100)",
    stop_atr_multiplier: "Experimental ATR stop multiplier (1.00, 1.25, or 1.50)",
    max_concurrent_positions: "Experimental max positions (1 to 5)",
  };

  return (
    <div className="min-w-0 space-y-4">
      <PageHeader
        eyebrow="Owner"
        title="Admin control center"
        description="Account, risk, strategy, and live authorization. Opening this page does not enable live trading."
      />
      {error ? (
        <p className="rounded-[var(--radius-os)] border border-[var(--danger)] px-3 py-2 text-sm" role="alert">
          {error}
        </p>
      ) : null}
      {notice ? (
        <p className="rounded-[var(--radius-os)] border border-[var(--border)] px-3 py-2 text-sm" role="status">
          {notice}
        </p>
      ) : null}
      <div className="grid gap-3 lg:grid-cols-3">
        <Card>
          <CardHeader><CardTitle className="text-sm">Owner</CardTitle></CardHeader>
          <CardContent className="space-y-1 text-xs text-[var(--fg-muted)]">
            <p>{overview?.owner?.email || "—"}</p>
            <p>Role {text(overview?.owner?.role)}</p>
            <Badge tone="warning">No other account can become owner here</Badge>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-sm">Broker</CardTitle></CardHeader>
          <CardContent className="space-y-1 text-xs text-[var(--fg-muted)]">
            <p>Ownership {text(broker.ownership)}</p>
            <p>Gateway {broker.gateway_online ? "online" : "offline"}</p>
            <p>MT5 {broker.mt5_attached ? "attached" : "not attached"}</p>
            <p>Server {text(broker.server)}</p>
            <p>Equity {text(broker.equity)}</p>
            <p>Positions {text(broker.open_positions)}</p>
            <Link className="text-[var(--accent)] underline" href="/broker">Open broker account controls</Link>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-sm">Release</CardTitle></CardHeader>
          <CardContent className="space-y-1 text-xs text-[var(--fg-muted)]">
            <p>Commit {overview?.deployment?.commit_sha || "—"}</p>
            <p>Policy v{text(policy?.version)} · {text(policy?.status)}</p>
            <p>Applied v{text(policy?.applied_version)}</p>
            <p>{policy ? policyStatusText(policy) : "—"}</p>
            <p>Source {text(policy?.source)}</p>
            <p>Live state {text(overview?.live_trading?.state)}</p>
            <Badge tone="neutral">24h evaluation stays on</Badge>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-3 lg:grid-cols-3">
        <Card>
          <CardHeader><CardTitle className="text-sm">Saved experimental settings</CardTitle></CardHeader>
          <CardContent className="text-xs text-[var(--fg-muted)]">
            <p>{states?.experimental || "No experimental settings are saved."}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-sm">Saved production policy</CardTitle></CardHeader>
          <CardContent className="text-xs text-[var(--fg-muted)]">
            <p>{states?.savedProduction || "No production policy is saved."}</p>
            <p>XAUUSD only. This restriction stays locked.</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-sm">Loaded by the live worker</CardTitle></CardHeader>
          <CardContent className="text-xs text-[var(--fg-muted)]">
            <p>{states?.workerLoaded || "The worker has not confirmed a saved version."}</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader><CardTitle>Risk and strategy</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <p className="text-xs text-[var(--fg-muted)]">
            Weekly loss stays off at 0 until you save a percent. Gold-only, protective stops, the kill switch, and the full UTC day cannot be turned off. A save does not arm live trading.
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            {POLICY_NUMERIC_KEYS.map((key) => (
              <label key={key} className="space-y-1 text-xs">
                <span className="text-[var(--fg-muted)]">{FIELD_LABELS[key]}</span>
                <Input
                  aria-label={FIELD_LABELS[key]}
                  value={draft[key] || ""}
                  onChange={(event) =>
                    setDraft((prev) => ({ ...prev, [key]: event.target.value }))
                  }
                />
              </label>
            ))}
          </div>
          <div className="grid gap-2 text-xs text-[var(--fg-muted)] sm:grid-cols-2">
            <p>Max concurrent positions: 1. This cap is saved and cannot be raised.</p>
            <p>Trading schedule: 00:00–23:59 UTC, seven days. Broker closures still block entries.</p>
            <p>Symbol: XAUUSD only. This cannot be turned off.</p>
            <p>Every new entry still requires a protective Stop Loss.</p>
          </div>
          <label className="block space-y-1 text-sm">
            <span>M1 micro-scalping</span>
            <select
              aria-label="M1 micro-scalping"
              className="block w-full rounded-[var(--radius-os)] border border-[var(--border)] bg-transparent px-2 py-1"
              value={m1}
              onChange={(event) => setM1(event.target.value as M1Choice)}
            >
              <option value="defer">Use deployment flag</option>
              <option value="on">On, if the deployment flag is on</option>
              <option value="off">Off</option>
            </select>
          </label>
          <label className="block space-y-1 text-sm">
            <span>M1 live submit</span>
            <select
              aria-label="M1 live submit"
              className="block w-full rounded-[var(--radius-os)] border border-[var(--border)] bg-transparent px-2 py-1"
              value={m1Live}
              onChange={(event) => setM1Live(event.target.value as M1Choice)}
            >
              <option value="defer">Use deployment flag</option>
              <option value="on">On, if execution is authorized</option>
              <option value="off">Off</option>
            </select>
          </label>
          <Button type="button" onClick={() => void savePolicy()} disabled={saving}>
            {saving ? "Saving" : "Save policy"}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Experimental policy</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <p className="text-xs text-[var(--fg-muted)]">
            This draft is not the live floor. Save experiment only stores it.
            Promote writes it into the saved production policy. Neither step
            shows it as loaded until the worker confirms that exact version.
            XAUUSD only stays locked.
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            {EXPERIMENTAL_KEYS.map((key) => (
              <label key={key} className="space-y-1 text-xs">
                <span className="text-[var(--fg-muted)]">{experimentLabels[key]}</span>
                <Input
                  aria-label={experimentLabels[key]}
                  value={experimentalDraft[key] || ""}
                  onChange={(event) =>
                    setExperimentalDraft((prev) => ({ ...prev, [key]: event.target.value }))
                  }
                />
              </label>
            ))}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="secondary"
              onClick={() => void saveExperimental(false)}
              disabled={saving}
            >
              Save experiment only
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => void saveExperimental(true)}
              disabled={saving}
            >
              Promote experiment
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Privileged audit</CardTitle></CardHeader>
        <CardContent>
          <ul className="space-y-2 text-xs">
            {(overview?.audit || []).slice(0, 12).map((row, index) => (
              <li key={`${text(row.occurred_at)}-${index}`} className="border-b border-[var(--border)] pb-2">
                {text(row.occurred_at)} · {text(row.action)} · {text(row.target)} · {text(row.outcome)} · {text(row.message)}
              </li>
            ))}
            {(overview?.audit || []).length === 0 ? <li>No privileged events yet.</li> : null}
          </ul>
        </CardContent>
      </Card>

      <LiveTradingControlPanel />
    </div>
  );
}
