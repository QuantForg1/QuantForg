"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DeskEmpty,
  DeskError,
  DeskSkeleton,
  DeskTable,
} from "@/components/desk/primitives";
import { NocPanel, NocRow } from "@/components/ops/noc/noc-primitives";
import { productionReliabilityApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { useAuth } from "@/providers/auth-provider";
import {
  canAccessIteOps,
  iteOpsAccessDeniedMessage,
} from "@/lib/auth/ite-ops-access";

type Section =
  | "overview"
  | "observability"
  | "reliability"
  | "incidents"
  | "backup"
  | "health"
  | "reports"
  | "security"
  | "performance";

function fmt(v: unknown, fallback = "—"): string {
  if (v === null || v === undefined || v === "") return fallback;
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (typeof v === "number") return Number.isFinite(v) ? String(v) : fallback;
  return String(v);
}

/**
 * Production Reliability & Operational Excellence — RC4 ops desk.
 * Additive observe-only. Never mutates trading / AI / OMS / MT5 / auth.
 */
export function ProductionReliabilityProgram() {
  const { user } = useAuth();
  const allowed = canAccessIteOps(user);
  const qc = useQueryClient();
  const [section, setSection] = useState<Section>("overview");
  const [title, setTitle] = useState("");
  const [severity, setSeverity] = useState("medium");

  const programQ = useQuery({
    queryKey: ["production-reliability-program"],
    queryFn: () => productionReliabilityApi.program(),
    enabled: allowed,
    refetchInterval: 15_000,
    retry: false,
  });

  const openInc = useMutation({
    mutationFn: () =>
      productionReliabilityApi.openIncident({
        title: title || "Untitled incident",
        severity,
        summary: "",
      }),
    onSuccess: () => {
      setTitle("");
      void qc.invalidateQueries({ queryKey: ["production-reliability-program"] });
    },
  });

  const setStatus = useMutation({
    mutationFn: (args: { id: string; status: string }) =>
      productionReliabilityApi.setIncidentStatus(args.id, {
        status: args.status,
        note: `transition → ${args.status}`,
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["production-reliability-program"] });
    },
  });

  const data = asRecord(programQ.data);
  const flags = asRecord(data.flags);
  const obs = asRecord(data.observability);
  const latencies = asRecord(obs.latencies_ms);
  const resources = asRecord(obs.resources);
  const reliability = asRecord(data.reliability);
  const incidents = asRecord(data.incidents);
  const incidentRows = asList(incidents.incidents);
  const backup = asRecord(data.backup_recovery);
  const checklist = asList(backup.checklist);
  const health = asRecord(data.production_health);
  const components = asRecord(health.components);
  const reports = asRecord(data.ops_reports);
  const security = asRecord(data.security_ops);
  const performance = asRecord(data.performance);
  const slowEndpoints = asList(performance.slow_endpoints);

  const sections = useMemo(
    () =>
      [
        ["overview", "Overview"],
        ["observability", "Observability"],
        ["reliability", "Reliability"],
        ["incidents", "Incidents"],
        ["backup", "Backup & DR"],
        ["health", "Health"],
        ["reports", "Reports"],
        ["security", "Security Ops"],
        ["performance", "Performance"],
      ] as const,
    [],
  );

  if (!allowed) {
    return (
      <DeskError
        message={iteOpsAccessDeniedMessage(
          user,
          undefined,
          "Production Reliability",
        )}
      />
    );
  }
  if (programQ.isLoading && !programQ.data) return <DeskSkeleton rows={12} />;
  if (programQ.error && !programQ.data) {
    return (
      <DeskError
        message={iteOpsAccessDeniedMessage(
          user,
          programQ.error,
          "Production Reliability",
        )}
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="accent">Reliability v1</Badge>
        <Badge tone="success">
          trading · {fmt(flags.modifies_trading, "false")}
        </Badge>
        <Badge tone="success">
          destructive · forbidden
        </Badge>
        <Button asChild size="sm" variant="outline">
          <Link href="/admin/noc">
            <Activity className="mr-1 size-3.5" />
            NOC
          </Link>
        </Button>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {sections.map(([id, label]) => (
          <Button
            key={id}
            size="sm"
            variant={section === id ? "secondary" : "ghost"}
            onClick={() => setSection(id)}
          >
            {label}
          </Button>
        ))}
      </div>

      {section === "overview" ? (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          <NocPanel id="rel-avail" title="Availability">
            <NocRow
              label="Availability %"
              value={fmt(reliability.availability_percent)}
            />
            <NocRow label="SLA met" value={fmt(reliability.sla_met)} />
            <NocRow label="SLO met" value={fmt(reliability.slo_met)} />
            <NocRow
              label="Error budget %"
              value={fmt(reliability.error_budget_remaining_percent)}
            />
          </NocPanel>
          <NocPanel id="rel-health" title="Production Health">
            <NocRow label="Overall" value={fmt(health.overall)} />
            <NocRow
              label="Components OK"
              value={`${fmt(health.ok_count)} / ${fmt(health.target_count)}`}
            />
            <NocRow label="Open incidents" value={fmt(reliability.open_incidents)} />
            <NocRow label="Success rate" value={fmt(obs.success_rate)} />
          </NocPanel>
          <NocPanel id="rel-sec" title="Security Ops">
            <NocRow label="Alerts" value={fmt(security.alert_count, "0")} />
            <NocRow
              label="Failed auth"
              value={fmt(security.failed_auth_count, "0")}
            />
            <NocRow
              label="Expired keys"
              value={fmt(security.expired_api_key_count, "0")}
            />
          </NocPanel>
        </div>
      ) : null}

      {section === "observability" ? (
        <div className="space-y-3">
          <NocPanel id="obs-lat" title="Latencies (ms)">
            {Object.keys(latencies).length === 0 ? (
              <DeskEmpty
                icon={Activity}
                title="No latency samples"
                description="Null means not measured — never fabricated."
              />
            ) : (
              Object.entries(latencies).map(([k, v]) => (
                <NocRow key={k} label={k} value={fmt(v)} />
              ))
            )}
          </NocPanel>
          <NocPanel id="obs-res" title="Resources">
            <NocRow label="CPU %" value={fmt(resources.cpu_percent)} />
            <NocRow label="Memory %" value={fmt(resources.memory_percent)} />
            <NocRow label="Memory MB" value={fmt(resources.memory_mb)} />
            <NocRow label="Error rate" value={fmt(obs.error_rate)} />
            <NocRow label="Success rate" value={fmt(obs.success_rate)} />
          </NocPanel>
        </div>
      ) : null}

      {section === "reliability" ? (
        <NocPanel id="rel-dash" title="Reliability Dashboard">
          <NocRow
            label="Availability %"
            value={fmt(reliability.availability_percent)}
          />
          <NocRow
            label="SLA target %"
            value={fmt(reliability.sla_target_percent)}
          />
          <NocRow
            label="SLO target %"
            value={fmt(reliability.slo_target_percent)}
          />
          <NocRow label="SLA met" value={fmt(reliability.sla_met)} />
          <NocRow label="SLO met" value={fmt(reliability.slo_met)} />
          <NocRow
            label="Error budget remaining %"
            value={fmt(reliability.error_budget_remaining_percent)}
          />
          <NocRow
            label="Incident count"
            value={fmt(reliability.incident_count)}
          />
          <NocRow
            label="Recovery time (s avg)"
            value={fmt(reliability.recovery_time_seconds_avg)}
          />
          <NocRow label="Failure rate" value={fmt(reliability.failure_rate)} />
        </NocPanel>
      ) : null}

      {section === "incidents" ? (
        <div className="space-y-3">
          <div className="flex flex-wrap items-end gap-2">
            <label className="text-[12px] text-[var(--muted-foreground)]">
              Title
              <input
                className="mt-1 block w-56 rounded border border-[var(--border)] bg-[var(--surface)] px-2 py-1 text-[13px]"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </label>
            <label className="text-[12px] text-[var(--muted-foreground)]">
              Severity
              <select
                className="mt-1 block rounded border border-[var(--border)] bg-[var(--surface)] px-2 py-1 text-[13px]"
                value={severity}
                onChange={(e) => setSeverity(e.target.value)}
              >
                <option value="low">low</option>
                <option value="medium">medium</option>
                <option value="high">high</option>
                <option value="critical">critical</option>
              </select>
            </label>
            <Button
              size="sm"
              onClick={() => openInc.mutate()}
              disabled={openInc.isPending}
            >
              Open incident
            </Button>
          </div>
          {incidentRows.length === 0 ? (
            <DeskEmpty
              icon={Activity}
              title="No incidents recorded"
              description="Open an incident to start the lifecycle timeline."
            />
          ) : (
            <DeskTable
              columns={["Title", "Status", "Severity", "Actions"]}
              rows={incidentRows.map((row) => {
                const r = asRecord(row);
                const id = str(r.id);
                return [
                  str(r.title, "—"),
                  str(r.status, "—"),
                  str(r.severity, "—"),
                  <div key={id} className="flex flex-wrap gap-1">
                    {(
                      [
                        "investigating",
                        "mitigated",
                        "resolved",
                        "postmortem",
                      ] as const
                    ).map((st) => (
                      <Button
                        key={st}
                        size="sm"
                        variant="ghost"
                        disabled={setStatus.isPending}
                        onClick={() => setStatus.mutate({ id, status: st })}
                      >
                        {st}
                      </Button>
                    ))}
                  </div>,
                ];
              })}
            />
          )}
        </div>
      ) : null}

      {section === "backup" ? (
        <div className="space-y-3">
          <NocPanel id="bak-status" title="Backup Status">
            <NocRow
              label="Directory exists"
              value={fmt(asRecord(backup.backup_status).backup_directory_exists)}
            />
            <NocRow
              label="Artifacts"
              value={fmt(asRecord(backup.backup_status).artifact_count, "0")}
            />
            <NocRow label="Destructive ops" value="forbidden" tone="ok" />
            <NocRow
              label="DR passed"
              value={`${fmt(backup.passed_count)} / ${fmt(backup.total)}`}
            />
          </NocPanel>
          {checklist.length === 0 ? (
            <DeskEmpty
              icon={Activity}
              title="DR checklist unavailable"
              description="Disaster recovery checklist loads from the program API."
            />
          ) : (
            <DeskTable
              columns={["ID", "Item", "Evidence pass"]}
              rows={checklist.map((row) => {
                const r = asRecord(row);
                return [
                  str(r.id),
                  str(r.item),
                  fmt(r.evidence_pass),
                ];
              })}
            />
          )}
        </div>
      ) : null}

      {section === "health" ? (
        <DeskTable
          columns={["Component", "Status", "OK", "Detail"]}
          rows={Object.entries(components).map(([name, row]) => {
            const r = asRecord(row);
            return [
              name,
              str(r.status, "—"),
              fmt(r.ok),
              str(r.detail, "—"),
            ];
          })}
        />
      ) : null}

      {section === "reports" ? (
        <div className="grid gap-3 md:grid-cols-2">
          {(
            [
              ["daily_health_report", "Daily Health"],
              ["weekly_reliability_report", "Weekly Reliability"],
              ["monthly_operations_report", "Monthly Operations"],
              ["quarterly_infrastructure_report", "Quarterly Infrastructure"],
            ] as const
          ).map(([key, label]) => {
            const r = asRecord(reports[key]);
            return (
              <NocPanel key={key} id={`rpt-${key}`} title={label}>
                <NocRow label="As of" value={fmt(r.as_of)} />
                <NocRow label="Availability" value={fmt(r.availability_percent)} />
                <NocRow label="Incidents" value={fmt(r.incident_count)} />
                <NocRow label="Error rate" value={fmt(r.error_rate)} />
                <NocRow label="SLA met" value={fmt(r.sla_met)} />
              </NocPanel>
            );
          })}
        </div>
      ) : null}

      {section === "security" ? (
        <div className="grid gap-3 md:grid-cols-2">
          <NocPanel id="sec-ops" title="Security Operations">
            <NocRow
              label="Suspicious signals"
              value={fmt(asList(security.suspicious_logins).length, "0")}
            />
            <NocRow
              label="Failed auth"
              value={fmt(security.failed_auth_count, "0")}
            />
            <NocRow
              label="API abuse"
              value={fmt(asList(security.api_abuse).length, "0")}
            />
            <NocRow
              label="Permission violations"
              value={fmt(security.permission_violation_count, "0")}
            />
            <NocRow
              label="Expired API keys"
              value={fmt(security.expired_api_key_count, "0")}
            />
            <NocRow label="Modifies auth" value="false" tone="ok" />
          </NocPanel>
        </div>
      ) : null}

      {section === "performance" ? (
        <div className="space-y-3">
          <NocPanel id="perf" title="Performance">
            <NocRow
              label="CPU %"
              value={fmt(asRecord(performance.cpu).percent)}
            />
            <NocRow
              label="Memory %"
              value={fmt(asRecord(performance.memory).percent)}
            />
            <NocRow
              label="Network sent"
              value={fmt(asRecord(performance.network).bytes_sent)}
            />
            <NocRow
              label="DB latency ms"
              value={fmt(asRecord(performance.database).latency_ms)}
            />
          </NocPanel>
          {slowEndpoints.length === 0 ? (
            <DeskEmpty
              icon={Activity}
              title="No slow endpoints"
              description="No channels above the 250ms latency threshold."
            />
          ) : (
            <DeskTable
              columns={["Channel", "Latency ms", "Threshold"]}
              rows={slowEndpoints.map((row) => {
                const r = asRecord(row);
                return [
                  str(r.endpoint_or_channel),
                  fmt(r.latency_ms),
                  fmt(r.threshold_ms),
                ];
              })}
            />
          )}
        </div>
      ) : null}
    </div>
  );
}
