"use client";

import { useQuery } from "@tanstack/react-query";
import { FlaskConical } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { replayEvidenceLabApi } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { formatNumber } from "@/lib/utils";

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-[var(--border)] bg-[var(--bg)]/40 px-2.5 py-2">
      <p className="text-[9px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
        {label}
      </p>
      <p className="mt-1 font-mono text-sm tabular text-[var(--fg)]">{value}</p>
    </div>
  );
}

function fmt(v: unknown, d = 2): string {
  const n = num(v);
  return Number.isFinite(n) ? formatNumber(n, d) : "—";
}

function fmtPct(v: unknown): string {
  const n = num(v);
  return Number.isFinite(n) ? `${formatNumber(n * 100, 1)}%` : "—";
}

/**
 * Institutional Replay & Evidence Lab desk — advisory only.
 * Never modifies strategy / risk / safety / execution / Performance IQ.
 */
export function ReplayEvidenceLabWorkspace() {
  const q = useQuery({
    queryKey: ["replay-evidence-lab"],
    queryFn: () => replayEvidenceLabApi.dashboard(),
    retry: false,
    staleTime: 20_000,
  });

  if (q.isLoading && !q.data) return <DeskSkeleton rows={8} />;
  if (q.isError) {
    return (
      <DeskError
        message="Replay & Evidence Lab unavailable."
        onRetry={() => void q.refetch()}
      />
    );
  }

  const d = asRecord(q.data);
  const summary = asRecord(d.evidence_summary);
  const evidence = asRecord(d.evidence);
  const lanes = asRecord(evidence.lanes);
  const gates = asRecord(d.gates);
  const checks = asList(gates.checks).map(asRecord);
  const confidence = asRecord(d.confidence);
  const laneSamples = asRecord(confidence.lane_samples);
  const kpis = asList(confidence.kpis).map(asRecord);
  const cf = asRecord(d.counterfactual);
  const hist = asRecord(cf.result_histogram);
  const recs = asList(d.recommendations).map(String);
  const openQ = asList(asRecord(d.reports).open_questions).map(String);
  const opps = asList(asRecord(d.replay).opportunities).map(asRecord);

  const empty =
    num(summary.replay_opportunities) === 0 &&
    num(summary.live_records) === 0 &&
    num(summary.bars_loaded) === 0;

  if (empty) {
    return (
      <DeskEmpty
        icon={FlaskConical}
        title="No replay evidence ingested"
        description="POST historical XAUUSD bars and tagged opportunities to /replay-evidence-lab/replay, or generate a local report via scripts/replay_evidence_lab.py --demo. Lanes stay empty rather than fabricated."
      />
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2 border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Replay & Evidence Lab
          </span>
          <Badge tone="neutral">v{str(d.version, "1.0.1")}</Badge>
          <Badge tone="neutral">
            confidence={str(confidence.overall_confidence, "—")}
          </Badge>
          <Badge tone={gates.all_passed ? "success" : "warning"}>
            gates {gates.all_passed ? "PASS" : "BLOCKED"}
          </Badge>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 md:grid-cols-4 lg:grid-cols-6">
        <Stat label="Bars" value={str(summary.bars_loaded, "0")} />
        <Stat label="Replay opps" value={str(summary.replay_opportunities, "0")} />
        <Stat label="Live" value={str(lanes.live ?? summary.live_records, "0")} />
        <Stat label="Demo" value={str(lanes.demo, "0")} />
        <Stat label="Research" value={str(lanes.research, "0")} />
        <Stat
          label="NO_TRADE obs"
          value={str(summary.no_trade_observations, "0")}
        />
      </div>

      <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
          Evidence lanes (never mixed)
        </h3>
        <div className="mt-2 grid grid-cols-2 gap-2 md:grid-cols-4">
          {(["live", "demo", "replay", "research"] as const).map((lane) => (
            <Stat key={lane} label={lane} value={str(lanes[lane], "0")} />
          ))}
        </div>
      </section>

      <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
          Confidence
        </h3>
        <div className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-3">
          {(["live_closed_trades", "replay_opportunities", "no_trade_observations"] as const).map(
            (key) => {
              const row = asRecord(laneSamples[key]);
              return (
                <div
                  key={key}
                  className="border border-[var(--border)] bg-[var(--bg)]/40 px-2.5 py-2"
                >
                  <p className="text-[9px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                    {key.replaceAll("_", " ")}
                  </p>
                  <p className="mt-1 font-mono text-sm tabular text-[var(--fg)]">
                    n={str(row.sample_size, "0")} · {str(row.confidence, "—")}
                  </p>
                  <p className="mt-0.5 font-mono text-[10px] text-[var(--fg-subtle)]">
                    coverage {fmtPct(row.coverage)}
                  </p>
                </div>
              );
            },
          )}
        </div>
        {kpis.length > 0 ? (
          <div className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-3">
            {kpis.map((k) => (
              <Stat
                key={str(k.name)}
                label={`${str(k.name)} (${str(k.confidence)})`}
                value={
                  typeof k.value === "number" && str(k.name).includes("rate")
                    ? fmtPct(k.value)
                    : fmt(k.value)
                }
              />
            ))}
          </div>
        ) : null}
      </section>

      <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
          Evidence gates (advisory)
        </h3>
        <ul className="mt-2 space-y-1">
          {checks.map((c) => (
            <li
              key={str(c.id)}
              className="flex flex-wrap items-center justify-between gap-2 border border-[var(--border)] bg-[var(--bg)]/40 px-2.5 py-1.5 text-[12px]"
            >
              <span>{str(c.label)}</span>
              <span className="font-mono tabular text-[var(--fg-subtle)]">
                {str(c.observed)}/{str(c.required)}{" "}
                {c.passed ? "PASS" : "FAIL"}
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
          Counterfactual (research only)
        </h3>
        <p className="mt-1 text-[11px] text-[var(--fg-subtle)]">
          Never feeds production KPIs. Same-bar SL+TP stays ambiguous.
        </p>
        <div className="mt-2 grid grid-cols-2 gap-2 md:grid-cols-4">
          <Stat label="NO_TRADE" value={str(cf.no_trade_count, "0")} />
          <Stat label="TP first" value={str(hist.tp_first, "0")} />
          <Stat label="SL first" value={str(hist.sl_first, "0")} />
          <Stat label="Neither" value={str(hist.neither, "0")} />
        </div>
      </section>

      {opps.length > 0 ? (
        <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
          <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
            Replay opportunities
          </h3>
          <div className="mt-2 max-h-48 overflow-auto">
            <table className="w-full text-left text-[11px]">
              <thead className="text-[var(--fg-subtle)]">
                <tr>
                  <th className="py-1 pr-2">Time</th>
                  <th className="py-1 pr-2">Session</th>
                  <th className="py-1 pr-2">Decision</th>
                  <th className="py-1 pr-2">Conf</th>
                  <th className="py-1">RR</th>
                </tr>
              </thead>
              <tbody>
                {opps.slice(0, 40).map((o, i) => (
                  <tr key={`${str(o.timestamp)}-${i}`} className="border-t border-[var(--border)]">
                    <td className="py-1 pr-2 font-mono">{str(o.timestamp, "—")}</td>
                    <td className="py-1 pr-2">{str(o.session, "—")}</td>
                    <td className="py-1 pr-2">{str(o.decision, "—")}</td>
                    <td className="py-1 pr-2 font-mono">{fmt(o.confluence_score, 0)}</td>
                    <td className="py-1 font-mono">{fmt(o.rr)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
          Recommendations
        </h3>
        <ul className="mt-2 list-disc space-y-1 pl-4 text-[12px] text-[var(--fg)]">
          {recs.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      </section>

      {openQ.length > 0 ? (
        <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
          <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
            Open questions
          </h3>
          <ul className="mt-2 list-disc space-y-1 pl-4 text-[12px] text-[var(--fg)]">
            {openQ.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
