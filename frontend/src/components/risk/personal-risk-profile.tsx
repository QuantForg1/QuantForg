"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { riskApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, str } from "@/lib/desk";
import { formatRelativeTime } from "@/lib/utils";

/**
 * Personal risk profile. Every value shown as "Enforced" is what the backend
 * trading engine installs for this user, not the text typed into the form.
 */

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] as const;

type FieldSpec = {
  key: string;
  label: string;
  unit: string;
  help: string;
  kind: string;
  default: unknown;
  min: unknown;
  max: unknown;
  off_allowed: boolean;
};

const GROUPS: Array<{ title: string; keys: string[] }> = [
  {
    title: "Position risk",
    keys: [
      "planned_risk_pct",
      "aggregate_open_risk_pct",
      "max_open_positions",
      "max_lot",
    ],
  },
  {
    title: "Loss protection",
    keys: [
      "daily_loss_pct",
      "weekly_loss_pct",
      "monthly_loss_pct",
      "max_drawdown_pct",
    ],
  },
  {
    title: "Entry quality & execution",
    keys: ["min_reward_risk", "max_spread", "min_trade_quality"],
  },
  { title: "Trading schedule", keys: ["trading_hours_utc", "trading_days"] },
];

function display(value: unknown, kind: string): string {
  if (Array.isArray(value)) {
    return value.map((d) => WEEKDAYS[Number(d)] ?? String(d)).join(", ");
  }
  const text = value == null ? "" : String(value);
  if (kind === "pct_off" && text.trim() !== "" && Number(text) === 0) {
    return "OFF";
  }
  return text;
}

function sameValue(a: unknown, b: unknown): boolean {
  if (Array.isArray(a) || Array.isArray(b)) {
    const left = asList(a).map(Number).sort();
    const right = asList(b).map(Number).sort();
    return JSON.stringify(left) === JSON.stringify(right);
  }
  const sa = String(a ?? "").trim();
  const sb = String(b ?? "").trim();
  const na = Number(sa);
  const nb = Number(sb);
  if (sa !== "" && sb !== "" && Number.isFinite(na) && Number.isFinite(nb)) {
    return na === nb;
  }
  return sa === sb;
}

function errorDetails(e: unknown): Record<string, string> {
  if (!(e instanceof ApiError)) return {};
  const fieldErrors = asRecord(asRecord(e.details).errors);
  return Object.fromEntries(
    Object.entries(fieldErrors).map(([k, v]) => [k, String(v)]),
  );
}

export function PersonalRiskProfile() {
  const qc = useQueryClient();
  const profileQ = useQuery({
    queryKey: ["risk-profile"],
    queryFn: () => riskApi.profile(),
    retry: false,
    staleTime: 10_000,
  });
  const eventsQ = useQuery({
    queryKey: ["risk-profile-events"],
    queryFn: () => riskApi.profileEvents(20),
    retry: false,
    staleTime: 30_000,
  });

  const data = asRecord(profileQ.data);
  const effective = asRecord(data.effective);
  const sources = asRecord(data.sources);
  const engine = asRecord(data.engine_policy);
  const fields = asList(data.fields).map(
    (f) => asRecord(f) as unknown as FieldSpec,
  );
  const specByKey: Record<string, FieldSpec> = Object.fromEntries(
    fields.map((f) => [f.key, f]),
  );
  const version = Number(data.version ?? 0);
  const warnings = asList(data.warnings).map((w) => String(w));
  const events = asList(asRecord(eventsQ.data).items).map(asRecord);

  const [draft, setDraft] = useState<Record<string, unknown>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  useEffect(() => {
    if (!profileQ.isSuccess) return;
    setDraft({ ...asRecord(asRecord(profileQ.data).effective) });
  }, [profileQ.isSuccess, profileQ.dataUpdatedAt, profileQ.data]);

  const changes = useMemo(() => {
    const out: Record<string, unknown> = {};
    for (const key of Object.keys(draft)) {
      if (!sameValue(draft[key], effective[key])) out[key] = draft[key];
    }
    return out;
  }, [draft, effective]);
  const dirty = Object.keys(changes).length > 0;

  const onDone = async (message: string) => {
    toast.success(message);
    setErrors({});
    await qc.invalidateQueries({ queryKey: ["risk-profile"] });
    await qc.invalidateQueries({ queryKey: ["risk-profile-events"] });
    await qc.invalidateQueries({ queryKey: ["risk-preferences"] });
  };
  const onFail = (e: unknown) => {
    setErrors(errorDetails(e));
    toast.error(
      e instanceof ApiError ? e.message : "Could not save your risk profile",
    );
  };

  const saveMut = useMutation({
    mutationFn: () =>
      riskApi.updateProfile({ changes, expected_version: version }),
    onSuccess: () =>
      onDone("Risk profile saved. It applies to your next trades."),
    onError: onFail,
  });
  const resetMut = useMutation({
    mutationFn: () => riskApi.resetProfile(version),
    onSuccess: () => onDone("Risk profile restored to the default values."),
    onError: onFail,
  });
  const resetField = useMutation({
    mutationFn: (key: string) =>
      riskApi.updateProfile({
        changes: { [key]: null },
        expected_version: version,
      }),
    onSuccess: () => onDone("Setting restored to its default."),
    onError: onFail,
  });

  const busy = saveMut.isPending || resetMut.isPending || resetField.isPending;

  const renderField = (key: string) => {
    const spec = specByKey[key];
    if (!spec) return null;
    const source = str(sources[key], "DEFAULT");
    const err = errors[key];
    const range =
      spec.min != null && spec.max != null
        ? `${spec.off_allowed ? "0 (OFF) or " : ""}${String(spec.min)}–${String(spec.max)}`
        : "";
    return (
      <div
        key={key}
        className="space-y-1.5 rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--bg)]/30 p-3"
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <Label htmlFor={`rp-${key}`}>{spec.label}</Label>
          <Badge tone={source === "CUSTOM" ? "accent" : "neutral"}>
            {source}
          </Badge>
        </div>
        {spec.kind === "days" ? (
          <div
            className="flex flex-wrap gap-1.5"
            role="group"
            aria-label={spec.label}
          >
            {WEEKDAYS.map((name, idx) => {
              const on = asList(draft[key]).map(Number).includes(idx);
              return (
                <button
                  key={name}
                  type="button"
                  aria-pressed={on}
                  disabled={busy}
                  onClick={() =>
                    setDraft((prev) => {
                      const cur = asList(prev[key]).map(Number);
                      const next = on
                        ? cur.filter((d) => d !== idx)
                        : [...cur, idx].sort((x, y) => x - y);
                      return { ...prev, [key]: next };
                    })
                  }
                  className={
                    "h-8 rounded-md border px-2.5 text-xs font-medium transition-colors " +
                    (on
                      ? "border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent)]"
                      : "border-[var(--border)] text-[var(--fg-muted)] hover:bg-[var(--surface-2)]")
                  }
                >
                  {name}
                </button>
              );
            })}
          </div>
        ) : (
          <Input
            id={`rp-${key}`}
            value={String(draft[key] ?? "")}
            disabled={busy}
            inputMode={spec.kind === "hours" ? "text" : "decimal"}
            aria-invalid={Boolean(err)}
            onChange={(e) =>
              setDraft((prev) => ({ ...prev, [key]: e.target.value }))
            }
          />
        )}
        <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-[var(--fg-subtle)]">
          <span>
            {spec.unit}
            {range ? ` · allowed ${range}` : ""} · default{" "}
            {display(spec.default, spec.kind)}
          </span>
          <span className="tabular text-[var(--fg-muted)]">
            Enforced:{" "}
            <strong className="text-[var(--fg)]">
              {display(effective[key], spec.kind)}
            </strong>
          </span>
        </div>
        <p className="text-[11px] text-[var(--fg-subtle)]">{spec.help}</p>
        {err ? (
          <p className="text-[11px] text-[var(--danger)]" role="alert">
            {err}
          </p>
        ) : null}
        {source === "CUSTOM" ? (
          <button
            type="button"
            className="text-[11px] text-[var(--accent)] underline-offset-2 hover:underline disabled:opacity-50"
            disabled={busy}
            onClick={() => resetField.mutate(key)}
          >
            Use default
          </button>
        ) : null}
      </div>
    );
  };

  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-3">
        <div>
          <CardTitle>My Risk Profile</CardTitle>
          <p className="mt-1 max-w-2xl text-xs text-[var(--fg-muted)]">
            These limits are yours alone and the robot applies them to your
            next trades. Settings you have not changed use the platform
            defaults. Open positions are never modified by a change here.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-[var(--fg-subtle)]">
            {data.updated_at
              ? `Updated ${formatRelativeTime(String(data.updated_at))}`
              : "Using defaults"}
          </span>
          <Badge tone="neutral">Profile v{version}</Badge>
          {engine.system_policy_version != null ? (
            <Badge tone="neutral">
              Policy v{String(engine.system_policy_version)}
            </Badge>
          ) : null}
          <Badge tone={dirty ? "warning" : "success"}>
            {dirty ? "Unsaved changes" : "In effect"}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        {profileQ.isError ? (
          <p className="text-sm text-[var(--danger)]" role="alert">
            Your risk profile could not be loaded. New trades stay blocked
            until it can be read; nothing is assumed.
          </p>
        ) : profileQ.isLoading ? (
          <div className="grid gap-3 md:grid-cols-2" aria-busy="true">
            {Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                className="h-24 animate-pulse rounded-md bg-[var(--surface-2)]"
              />
            ))}
          </div>
        ) : (
          <>
            {warnings.length ? (
              <div
                role="status"
                className="space-y-1 rounded-[var(--radius-os)] border border-[color-mix(in_srgb,var(--warning)_40%,var(--border))] bg-[var(--warning-soft)] px-3 py-2.5 text-xs text-[var(--fg)]"
              >
                <p className="font-semibold text-[var(--warning)]">
                  Aggressive settings
                </p>
                {warnings.map((w) => (
                  <p key={w}>{w}</p>
                ))}
                <p className="text-[var(--fg-muted)]">
                  Higher risk settings do not guarantee higher returns.
                </p>
              </div>
            ) : null}
            {GROUPS.map((group) => (
              <section
                key={group.title}
                aria-label={group.title}
                className="space-y-2"
              >
                <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                  {group.title}
                </h3>
                <div className="grid gap-3 md:grid-cols-2">
                  {group.keys.map(renderField)}
                </div>
              </section>
            ))}
            <div className="rounded-[var(--radius-os)] border border-[var(--border)] px-3 py-2.5 text-[11px] text-[var(--fg-muted)]">
              Always enforced for every account: mandatory broker-side
              stop-loss, gold only, broker minimum lot / step / margin /
              market hours, no martingale, no grid recovery, no forced trades.
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                disabled={!dirty || busy}
                onClick={() => saveMut.mutate()}
              >
                {saveMut.isPending ? "Saving…" : "Save changes"}
              </Button>
              <Button
                type="button"
                variant="ghost"
                disabled={!dirty || busy}
                onClick={() => {
                  setDraft({ ...effective });
                  setErrors({});
                }}
              >
                Discard
              </Button>
              <Button
                type="button"
                variant="outline"
                disabled={busy || version === 0}
                onClick={() => {
                  if (
                    window.confirm(
                      "Restore every risk setting to the default values?",
                    )
                  ) {
                    resetMut.mutate();
                  }
                }}
              >
                Reset to defaults
              </Button>
            </div>
            {events.length ? (
              <details className="text-xs text-[var(--fg-muted)]">
                <summary className="cursor-pointer select-none">
                  Change history
                </summary>
                <ul className="mt-2 space-y-1">
                  {events.map((ev, i) => (
                    <li key={`${str(ev.created_at)}-${i}`}>
                      v{String(ev.version)} · {str(ev.action)} ·{" "}
                      {ev.created_at
                        ? formatRelativeTime(String(ev.created_at))
                        : ""}
                    </li>
                  ))}
                </ul>
              </details>
            ) : null}
          </>
        )}
      </CardContent>
    </Card>
  );
}
