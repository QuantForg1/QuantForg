"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DeskEmpty,
  DeskError,
  DeskSkeleton,
  DeskTable,
} from "@/components/desk/primitives";
import { NocPanel, NocRow } from "@/components/ops/noc/noc-primitives";
import { enterpriseApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { useAuth } from "@/providers/auth-provider";
import {
  canAccessIteOps,
  iteOpsAccessDeniedMessage,
} from "@/lib/auth/ite-ops-access";

type Section =
  | "dashboard"
  | "organizations"
  | "rbac"
  | "api_keys"
  | "audit"
  | "security"
  | "reports"
  | "compliance"
  | "admin";

function fmt(v: unknown, fallback = "—"): string {
  if (v === null || v === undefined || v === "") return fallback;
  if (typeof v === "boolean") return v ? "yes" : "no";
  return String(v);
}

/**
 * QuantForg Enterprise Platform — RC4 executive desk.
 * Additive SaaS controls. Never mutates trading / AI / OMS / MT5 / COP / auth.
 */
export function EnterprisePlatform() {
  const { user } = useAuth();
  const allowed = canAccessIteOps(user);
  const qc = useQueryClient();
  const [section, setSection] = useState<Section>("dashboard");
  const [orgId, setOrgId] = useState("platform");
  const [keyName, setKeyName] = useState("Ops key");
  const [onceSecret, setOnceSecret] = useState<string | null>(null);
  const [gdprUser, setGdprUser] = useState("");

  const platformQ = useQuery({
    queryKey: ["enterprise-platform"],
    queryFn: () => enterpriseApi.platform(),
    enabled: allowed,
    refetchInterval: 20_000,
    retry: false,
  });

  const createKey = useMutation({
    mutationFn: () =>
      enterpriseApi.createApiKey({
        organization_id: orgId || "platform",
        name: keyName || "API key",
        scopes: ["read:dashboard", "read:reports"],
        expires_days: 90,
      }),
    onSuccess: (data) => {
      const r = asRecord(data);
      setOnceSecret(str(r.plaintext, ""));
      void qc.invalidateQueries({ queryKey: ["enterprise-platform"] });
    },
  });

  const gdpr = useMutation({
    mutationFn: () => enterpriseApi.gdprExport(gdprUser),
  });

  const data = asRecord(platformQ.data);
  const flags = asRecord(data.flags);
  const dashboard = asRecord(data.dashboard);
  const metrics = asRecord(dashboard.metrics);
  const orgs = asRecord(data.organizations);
  const orgRows = asList(orgs.organizations);
  const rbac = asRecord(data.rbac);
  const rbacRows = asList(rbac.rows);
  const apiKeys = asRecord(data.api_keys);
  const keyRows = asList(apiKeys.keys);
  const audit = asRecord(data.audit_center);
  const timeline = asList(audit.timeline);
  const security = asRecord(data.security_center);
  const sessions = asList(security.sessions);
  const devices = asList(security.devices);
  const alerts = asList(security.security_alerts);
  const reports = asRecord(data.reports);
  const compliance = asRecord(data.compliance);
  const admin = asRecord(data.admin_console);

  const sections = useMemo(
    () =>
      [
        ["dashboard", "Dashboard"],
        ["organizations", "Organizations"],
        ["rbac", "RBAC"],
        ["api_keys", "API Keys"],
        ["audit", "Audit"],
        ["security", "Security"],
        ["reports", "Reports"],
        ["compliance", "Compliance"],
        ["admin", "Admin"],
      ] as const,
    [],
  );

  if (!allowed) {
    return (
      <DeskError
        message={iteOpsAccessDeniedMessage(
          user,
          undefined,
          "Enterprise Platform",
        )}
      />
    );
  }
  if (platformQ.isLoading && !platformQ.data) return <DeskSkeleton rows={12} />;
  if (platformQ.error && !platformQ.data) {
    return (
      <DeskError
        message={iteOpsAccessDeniedMessage(
          user,
          platformQ.error,
          "Enterprise Platform",
        )}
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="accent">Enterprise v1</Badge>
        <Badge tone="success">
          trading · {fmt(flags.modifies_trading, "false")}
        </Badge>
        <Badge tone="success">auth · {fmt(flags.modifies_auth, "false")}</Badge>
        <Button asChild size="sm" variant="outline">
          <Link href="/admin/noc">NOC</Link>
        </Button>
        <Button asChild size="sm" variant="outline">
          <Link href="/admin/customer-ops">COP</Link>
        </Button>
      </div>

      <div className="flex flex-wrap gap-1 border border-[var(--border)] bg-[var(--surface)] p-1">
        {sections.map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => setSection(id)}
            className={
              section === id
                ? "bg-[var(--accent)]/15 px-3 py-1.5 text-[11px] uppercase tracking-[0.12em] text-[var(--accent)]"
                : "px-3 py-1.5 text-[11px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]"
            }
          >
            {label}
          </button>
        ))}
      </div>

      {section === "dashboard" ? (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <NocPanel title="Organizations">
              <p className="font-mono text-lg">{fmt(metrics.organizations, "0")}</p>
            </NocPanel>
            <NocPanel title="Active users">
              <p className="font-mono text-lg">{fmt(metrics.active_users, "0")}</p>
            </NocPanel>
            <NocPanel title="Active sessions">
              <p className="font-mono text-lg">
                {fmt(metrics.active_sessions, "0")}
              </p>
            </NocPanel>
            <NocPanel title="API keys">
              <p className="font-mono text-lg">
                {fmt(metrics.active_api_keys, "0")}
              </p>
            </NocPanel>
          </div>
          <NocPanel title="Executive Dashboard">
            <NocRow label="Gateway" value={fmt(metrics.gateway)} />
            <NocRow label="Robot online" value={fmt(metrics.robot_online)} />
            <NocRow
              label="Fabricated"
              value={fmt(dashboard.fabricated, "false")}
              tone="ok"
            />
            <NocRow
              label="Trading unchanged"
              value={fmt(dashboard.trading_behaviour_unchanged, "true")}
              tone="ok"
            />
          </NocPanel>
        </>
      ) : null}

      {section === "organizations" ? (
        <NocPanel title="Enterprise Organizations">
          {orgRows.length === 0 ? (
            <DeskEmpty
              icon={Building2}
              title="No organizations"
              description="Create a workspace under /organizations. Isolation namespaces appear per org."
              actionLabel="Organizations"
              actionHref="/organizations"
            />
          ) : (
            <DeskTable
              columns={["Name", "Slug", "Members", "Isolation"]}
              rows={orgRows.slice(0, 40).map((row) => {
                const r = asRecord(row);
                return [
                  fmt(r.name),
                  fmt(r.slug),
                  fmt(r.member_count, "0"),
                  fmt(asRecord(r.isolation).audit),
                ];
              })}
            />
          )}
        </NocPanel>
      ) : null}

      {section === "rbac" ? (
        <NocPanel title="Permission Matrix" action={<Badge tone="neutral">checked</Badge>}>
          {rbacRows.length === 0 ? (
            <p className="text-[12px] text-[var(--fg-muted)]">No matrix.</p>
          ) : (
            <DeskTable
              columns={[
                "Capability",
                "Owner",
                "Admin",
                "Trader",
                "Risk",
                "Support",
                "RO",
              ]}
              rows={rbacRows.slice(0, 40).map((row) => {
                const r = asRecord(row);
                return [
                  fmt(r.capability),
                  fmt(r.owner),
                  fmt(r.admin),
                  fmt(r.trader),
                  fmt(r.risk_manager),
                  fmt(r.support),
                  fmt(r.read_only),
                ];
              })}
            />
          )}
          <NocRow
            label="Replaces auth"
            value={fmt(rbac.replaces_auth, "false")}
            tone="ok"
          />
        </NocPanel>
      ) : null}

      {section === "api_keys" ? (
        <NocPanel
          title="API Key Management"
          action={
            <Badge tone="success">
              secrets · {fmt(apiKeys.never_exposes_secrets, "true")}
            </Badge>
          }
        >
          <div className="mb-3 flex flex-wrap gap-2">
            <input
              className="border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5 text-[12px]"
              placeholder="Organization id"
              value={orgId}
              onChange={(e) => setOrgId(e.target.value)}
            />
            <input
              className="border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5 text-[12px]"
              placeholder="Key name"
              value={keyName}
              onChange={(e) => setKeyName(e.target.value)}
            />
            <Button
              size="sm"
              disabled={createKey.isPending}
              onClick={() => createKey.mutate()}
            >
              Generate
            </Button>
          </div>
          {onceSecret ? (
            <p className="mb-3 break-all border border-[var(--warning)]/40 bg-[var(--warning-soft)] p-2 font-mono text-[11px] text-[var(--warning)]">
              Copy now (shown once): {onceSecret}
            </p>
          ) : null}
          {keyRows.length === 0 ? (
            <p className="text-[12px] text-[var(--fg-muted)]">No API keys.</p>
          ) : (
            <DeskTable
              columns={["Name", "Prefix", "Status", "Scopes", "Expires"]}
              rows={keyRows.slice(0, 40).map((row) => {
                const r = asRecord(row);
                return [
                  fmt(r.name),
                  fmt(r.prefix),
                  fmt(r.status),
                  Array.isArray(r.scopes) ? r.scopes.join(", ") : "—",
                  fmt(r.expires_at),
                ];
              })}
            />
          )}
        </NocPanel>
      ) : null}

      {section === "audit" ? (
        <NocPanel title="Audit Center">
          {timeline.length === 0 ? (
            <p className="text-[12px] text-[var(--fg-muted)]">
              Timeline aggregates enterprise, platform, and COP audit sources.
            </p>
          ) : (
            <DeskTable
              columns={["Time", "Source", "Action", "Operator", "Target"]}
              rows={timeline.slice(0, 50).map((row) => {
                const r = asRecord(row);
                return [
                  fmt(r.timestamp),
                  fmt(r.source),
                  fmt(r.action),
                  fmt(r.operator).slice(0, 16),
                  fmt(r.target).slice(0, 20),
                ];
              })}
            />
          )}
        </NocPanel>
      ) : null}

      {section === "security" ? (
        <div className="grid gap-3 lg:grid-cols-2">
          <NocPanel title="Sessions">
            <NocRow
              label="Active"
              value={fmt(security.active_sessions, "0")}
            />
            <DeskTable
              columns={["IP", "Active", "Last seen"]}
              rows={sessions.slice(0, 12).map((row) => {
                const r = asRecord(row);
                return [fmt(r.ip), fmt(r.is_active), fmt(r.last_seen_at)];
              })}
            />
          </NocPanel>
          <NocPanel title="Devices · MFA · Alerts">
            <NocRow label="Devices" value={fmt(security.device_count, "0")} />
            <NocRow
              label="MFA"
              value={fmt(asRecord(security.mfa).status)}
            />
            <NocRow
              label="IPs"
              value={fmt(security.ip_count, "0")}
            />
            {alerts.length === 0 ? (
              <p className="mt-2 text-[12px] text-[var(--fg-muted)]">
                No security alerts.
              </p>
            ) : (
              <DeskTable
                columns={["Severity", "Code", "Message"]}
                rows={alerts.slice(0, 8).map((row) => {
                  const r = asRecord(row);
                  return [fmt(r.severity), fmt(r.code), fmt(r.message)];
                })}
              />
            )}
            <p className="mt-2 text-[11px] text-[var(--fg-muted)]">
              Devices: {devices.length} observed · auth unmodified
            </p>
          </NocPanel>
        </div>
      ) : null}

      {section === "reports" ? (
        <div className="grid gap-3 lg:grid-cols-2">
          {(
            ["executive", "operational", "risk", "compliance", "support"] as const
          ).map((key) => {
            const r = asRecord(reports[key]);
            return (
              <NocPanel key={key} title={fmt(r.title, key)}>
                <pre className="overflow-auto whitespace-pre-wrap font-mono text-[11px] text-[var(--fg-muted)]">
                  {JSON.stringify(r, null, 2)}
                </pre>
              </NocPanel>
            );
          })}
        </div>
      ) : null}

      {section === "compliance" ? (
        <NocPanel title="Compliance">
          <NocRow
            label="GDPR export"
            value={fmt(compliance.gdpr_export_supported, "true")}
            tone="ok"
          />
          <NocRow
            label="Audit retention (days)"
            value={fmt(
              asRecord(compliance.retention).audit_retention_days,
              "365",
            )}
          />
          <NocRow
            label="Integrity"
            value={fmt(asRecord(compliance.integrity).integrity, "ok")}
            tone="ok"
          />
          <div className="mt-3 flex gap-2">
            <input
              className="min-w-[240px] flex-1 border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5 font-mono text-[12px]"
              placeholder="User UUID for GDPR export"
              value={gdprUser}
              onChange={(e) => setGdprUser(e.target.value.trim())}
            />
            <Button
              size="sm"
              disabled={!gdprUser || gdpr.isPending}
              onClick={() => gdpr.mutate()}
            >
              Export
            </Button>
          </div>
          {gdpr.data ? (
            <pre className="mt-3 max-h-48 overflow-auto font-mono text-[10px] text-[var(--fg-muted)]">
              {JSON.stringify(gdpr.data, null, 2)}
            </pre>
          ) : null}
        </NocPanel>
      ) : null}

      {section === "admin" ? (
        <NocPanel title="System Administration">
          <NocRow
            label="Users"
            value={fmt(asRecord(admin.users).count, "0")}
          />
          <NocRow
            label="Organizations"
            value={fmt(asRecord(admin.organizations).count, "0")}
          />
          <NocRow
            label="Broker fleet connected"
            value={fmt(
              asRecord(admin.infrastructure).broker_fleet_connected,
              "—",
            )}
          />
          <div className="mt-3 flex flex-wrap gap-2">
            {Object.entries(
              asRecord(asRecord(admin.infrastructure).links) as Record<
                string,
                unknown
              >,
            ).map(([k, href]) => (
              <Button key={k} asChild size="sm" variant="outline">
                <Link href={String(href)}>{k}</Link>
              </Button>
            ))}
          </div>
          <NocRow
            label="Modifies COP"
            value={fmt(admin.modifies_cop, "false")}
            tone="ok"
          />
        </NocPanel>
      ) : null}
    </div>
  );
}
