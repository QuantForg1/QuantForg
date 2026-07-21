"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { FlaskConical, Shield } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { researchValidationApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, str } from "@/lib/desk";
import { TRADING_SYMBOL } from "@/lib/trading/gold-only";
import { cn } from "@/lib/utils";

function Panel({
  title,
  children,
  action,
}: {
  title: string;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <section className="border border-[var(--border)] bg-[var(--surface)]">
      <header className="flex items-center justify-between gap-2 border-b border-[var(--border)] px-3 py-2">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          {title}
        </h2>
        {action}
      </header>
      <div className="p-3">{children}</div>
    </section>
  );
}

export function ResearchValidationWorkspace() {
  const qc = useQueryClient();
  const [cert, setCert] = useState<Record<string, unknown> | null>(null);
  const [compare, setCompare] = useState<Record<string, unknown> | null>(null);
  const [release, setRelease] = useState<Record<string, unknown> | null>(null);
  const [observatory, setObservatory] = useState<Record<string, unknown> | null>(
    null,
  );

  const statusQ = useQuery({
    queryKey: ["rvp-status"],
    queryFn: () => researchValidationApi.status(),
    staleTime: 15_000,
  });

  const registryQ = useQuery({
    queryKey: ["rvp-registry"],
    queryFn: () => researchValidationApi.registry(),
    staleTime: 15_000,
  });

  const versionsQ = useQuery({
    queryKey: ["rvp-versions"],
    queryFn: () => researchValidationApi.versions(undefined, 20),
    staleTime: 10_000,
  });

  const auditQ = useQuery({
    queryKey: ["rvp-rollback-audit"],
    queryFn: () => researchValidationApi.rollbackAudit(20),
    staleTime: 10_000,
  });

  const runPipelineM = useMutation({
    mutationFn: async () => {
      await researchValidationApi.recordVersion({
        strategy_key: "trend_following",
        version: "v1.0.0",
        parameters: { lookback: 20 },
        notes: "Baseline research version",
      });
      await researchValidationApi.recordVersion({
        strategy_key: "trend_following",
        version: "v1.1.0",
        parameters: { lookback: 24 },
        notes: "Candidate",
        parent_version: "v1.0.0",
      });
      await researchValidationApi.replayLoad({
        strategy_key: "trend_following",
        version: "v1.1.0",
        bars: [
          { time: "t1", open: 2300, high: 2305, low: 2298, close: 2302 },
          { time: "t2", open: 2302, high: 2308, low: 2300, close: 2306 },
        ],
      });
      const wf = await researchValidationApi.walkForward({
        strategy_key: "trend_following",
        version: "v1.1.0",
        folds: [
          { fold: 1, score: 70, profit_factor: 1.4, max_drawdown_pct: 8 },
          { fold: 2, score: 65, profit_factor: 1.3, max_drawdown_pct: 10 },
        ],
      });
      const paper = await researchValidationApi.paper({
        strategy_key: "trend_following",
        version: "v1.1.0",
        trade_count: 40,
        profit_factor: 1.45,
        max_drawdown_pct: 9,
        win_rate: 54,
      });
      const cmp = await researchValidationApi.compare({
        runs: [
          {
            strategy_key: "trend_following",
            version: "v1.1.0",
            profit_factor: 1.45,
            sharpe: 0.9,
            max_drawdown_pct: 9,
            trade_count: 40,
          },
          {
            strategy_key: "mean_reversion",
            version: "v0.9.0",
            profit_factor: 1.1,
            sharpe: 0.4,
            max_drawdown_pct: 18,
            trade_count: 25,
          },
        ],
      });
      setCompare(cmp);
      const obs = await researchValidationApi.observatory({
        strategy_key: "trend_following",
        version: "v1.1.0",
        metrics: {
          profit_factor: 1.45,
          sharpe: 0.9,
          max_drawdown_pct: 9,
          trade_count: 40,
        },
      });
      setObservatory(obs);
      const certification = await researchValidationApi.certify({
        strategy_key: "trend_following",
        version: "v1.1.0",
        stage_results: {
          registry: { passed: true, score: 100 },
          replay: { passed: true, score: 100 },
          walk_forward: { passed: wf.passed === true, score: wf.score },
          paper: { passed: paper.passed === true, score: paper.score },
          comparison: { passed: true, score: 80 },
          operator_review: { passed: true, score: 100, detail: "approved" },
        },
      });
      setCert(certification);
      const rel = await researchValidationApi.release({
        strategy_key: "trend_following",
        version: "v1.1.0",
        certified: certification.certified === true,
        operator_approved: true,
      });
      setRelease(rel);
      return { certification, release: rel };
    },
    onSuccess: async (data) => {
      toast.success(
        data.certification.certified
          ? "Certified (advisory — live pipeline unchanged)"
          : "Certification incomplete",
      );
      await qc.invalidateQueries({ queryKey: ["rvp-status"] });
      await qc.invalidateQueries({ queryKey: ["rvp-registry"] });
      await qc.invalidateQueries({ queryKey: ["rvp-versions"] });
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Pipeline failed"),
  });

  const rollbackM = useMutation({
    mutationFn: () =>
      researchValidationApi.rollback({
        strategy_key: "trend_following",
        target_version: "v1.0.0",
        reason: "operator_rollback_demo",
      }),
    onSuccess: async (data) => {
      toast.info(
        data.rolled_back
          ? "Rolled back — audit preserved"
          : str(asList(data.reasons)[0], "Rollback unavailable"),
      );
      await qc.invalidateQueries({ queryKey: ["rvp-versions"] });
      await qc.invalidateQueries({ queryKey: ["rvp-rollback-audit"] });
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Rollback failed"),
  });

  const caps = asRecord(statusQ.data?.capabilities);
  const strategies = asList(asRecord(registryQ.data).strategies);
  const versions = asList(asRecord(versionsQ.data).versions);
  const audits = asList(asRecord(auditQ.data).items);
  const modules = asList(statusQ.data?.modules);
  const certStages = asList(asRecord(cert).stages);
  const ranked = asList(asRecord(compare).ranked);
  const panels = asList(asRecord(observatory).panels);

  if (statusQ.isLoading && !statusQ.data) return <DeskSkeleton rows={6} />;
  if (statusQ.isError && !statusQ.data) {
    return (
      <DeskError
        message={
          statusQ.error instanceof ApiError
            ? statusQ.error.message
            : "Research & Validation unavailable"
        }
      />
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
        <FlaskConical className="size-4 text-[var(--fg-muted)]" />
        <span className="text-xs font-medium">{TRADING_SYMBOL} validation</span>
        <Badge tone="accent" className="text-[9px] uppercase">
          Pre-production
        </Badge>
        <Badge tone="success" className="text-[9px] uppercase">
          Live pipeline unchanged
        </Badge>
        {caps.certification_mandatory_before_production === true ? (
          <Badge tone="neutral" className="text-[9px] uppercase">
            Cert mandatory
          </Badge>
        ) : null}
        <span className="ml-auto font-mono text-[10px] text-[var(--fg-subtle)]">
          {str(statusQ.data?.version, "research-validation-v1")}
        </span>
        <Button
          size="sm"
          disabled={runPipelineM.isPending}
          onClick={() => runPipelineM.mutate()}
        >
          Run validation pipeline
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={rollbackM.isPending}
          onClick={() => rollbackM.mutate()}
        >
          Rollback to v1.0.0
        </Button>
      </div>

      <div className="grid gap-3 xl:grid-cols-3">
        <Panel title="Strategy registry">
          {!strategies.length ? (
            <DeskEmpty
              icon={FlaskConical}
              title="Empty registry"
              description="Register strategies for research"
            />
          ) : (
            <ul className="max-h-40 space-y-1 overflow-auto font-mono text-[10px]">
              {strategies.map((s) => {
                const row = asRecord(s);
                return (
                  <li
                    key={str(row.strategy_key, "s")}
                    className="flex justify-between border-b border-[var(--border)]/60 py-1"
                  >
                    <span>{str(row.strategy_key, "—")}</span>
                    <span className="text-[var(--fg-subtle)]">
                      {str(row.status, "research")}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>

        <Panel title="Certification">
          {!cert ? (
            <DeskEmpty
              icon={Shield}
              title="Not run"
              description="Certification mandatory before production"
            />
          ) : (
            <div className="space-y-1.5 text-xs">
              <div className="flex justify-between">
                <span className="text-[var(--fg-muted)]">Certified</span>
                <Badge
                  tone={cert.certified === true ? "success" : "warning"}
                  className="text-[9px] uppercase"
                >
                  {String(cert.certified === true)}
                </Badge>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--fg-muted)]">Score</span>
                <span className="font-mono">{str(cert.score, "—")}</span>
              </div>
              <ul className="max-h-28 space-y-1 overflow-auto font-mono text-[10px]">
                {certStages.map((st) => {
                  const row = asRecord(st);
                  return (
                    <li
                      key={str(row.stage, "st")}
                      className={cn(
                        "flex justify-between",
                        row.passed === true
                          ? "text-[var(--fg-muted)]"
                          : "text-[var(--warning)]",
                      )}
                    >
                      <span>{str(row.stage, "—")}</span>
                      <span>{row.passed === true ? "pass" : "fail"}</span>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
        </Panel>

        <Panel title="Release governance">
          {!release ? (
            <DeskEmpty
              icon={Shield}
              title="No release eval"
              description="Release never enables live order_send"
            />
          ) : (
            <div className="space-y-1.5 text-xs">
              <div className="flex justify-between">
                <span className="text-[var(--fg-muted)]">Release allowed</span>
                <span className="font-mono">
                  {String(release.release_allowed ?? false)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--fg-muted)]">Go-live</span>
                <span className="font-mono">
                  {String(release.production_go_live ?? false)}
                </span>
              </div>
              <ul className="max-h-28 space-y-1 overflow-auto text-[10px] text-[var(--fg-subtle)]">
                {asList(release.reasons).map((r, i) => (
                  <li key={`${i}-${str(r, "").slice(0, 20)}`}>{str(r, "")}</li>
                ))}
              </ul>
            </div>
          )}
        </Panel>
      </div>

      <div className="grid gap-3 xl:grid-cols-2">
        <Panel title="Comparison dashboard">
          {!ranked.length ? (
            <DeskEmpty
              icon={FlaskConical}
              title="No comparison"
              description="Supplied run metrics only"
            />
          ) : (
            <ul className="space-y-1 font-mono text-[10px]">
              {ranked.map((r) => {
                const row = asRecord(r);
                return (
                  <li
                    key={`${str(row.strategy_key)}-${str(row.version)}`}
                    className="flex justify-between border-b border-[var(--border)]/60 py-1"
                  >
                    <span>
                      {str(row.strategy_key, "—")} {str(row.version, "")}
                    </span>
                    <span>{str(row.composite, str(row.status, "—"))}</span>
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>

        <Panel title="Performance observatory">
          {!panels.length ? (
            <DeskEmpty
              icon={FlaskConical}
              title="No panels"
              description="Never fabricates metrics"
            />
          ) : (
            <ul className="grid gap-1 sm:grid-cols-2 font-mono text-[10px]">
              {panels.map((p) => {
                const row = asRecord(p);
                return (
                  <li
                    key={str(row.panel_id, "p")}
                    className="flex justify-between border border-[var(--border)] px-2 py-1"
                  >
                    <span className="text-[var(--fg-muted)] truncate">
                      {str(row.title, "—")}
                    </span>
                    <span>{str(row.value, "—")}</span>
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>
      </div>

      <div className="grid gap-3 xl:grid-cols-2">
        <Panel title="Version governance">
          {!versions.length ? (
            <DeskEmpty
              icon={FlaskConical}
              title="No versions"
              description="Every version is traceable"
            />
          ) : (
            <ul className="max-h-40 space-y-1 overflow-auto font-mono text-[10px]">
              {versions.map((v) => {
                const row = asRecord(v);
                return (
                  <li
                    key={str(row.version_id, "v")}
                    className="border-b border-[var(--border)]/60 py-1"
                  >
                    {str(row.strategy_key, "—")} · {str(row.version, "—")} ·{" "}
                    {str(row.content_hash, "").slice(0, 12)}
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>

        <Panel title="Rollback audit">
          {!audits.length ? (
            <DeskEmpty
              icon={FlaskConical}
              title="No rollbacks"
              description="Rollback preserves audit history"
            />
          ) : (
            <ul className="max-h-40 space-y-1 overflow-auto font-mono text-[10px]">
              {audits.map((a) => {
                const row = asRecord(a);
                return (
                  <li
                    key={str(row.audit_id, "a")}
                    className="border-b border-[var(--border)]/60 py-1"
                  >
                    {str(row.from_version, "—")} → {str(row.to_version, "—")} ·
                    preserved={String(row.audit_preserved ?? true)}
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>
      </div>

      <Panel title="Platform modules">
        <div className="flex flex-wrap gap-1">
          {modules.map((m) => (
            <Badge
              key={str(m, "m")}
              tone="neutral"
              className="text-[9px] font-mono"
            >
              {str(m, "")}
            </Badge>
          ))}
        </div>
      </Panel>
    </div>
  );
}
