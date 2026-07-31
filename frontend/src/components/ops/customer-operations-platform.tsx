"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskEmpty, DeskError, DeskSkeleton, DeskTable } from "@/components/desk/primitives";
import { NocPanel, NocRow } from "@/components/ops/noc/noc-primitives";
import { customerOpsApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { useAuth } from "@/providers/auth-provider";
import {
  canAccessIteOps,
  iteOpsAccessDeniedMessage,
} from "@/lib/auth/ite-ops-access";

type Section =
  | "fleet"
  | "licenses"
  | "brokers"
  | "support"
  | "notifications"
  | "analytics"
  | "audit"
  | "workspace";

function fmt(v: unknown, fallback = "—"): string {
  if (v === null || v === undefined || v === "") return fallback;
  if (typeof v === "boolean") return v ? "yes" : "no";
  return String(v);
}

/**
 * Institutional Customer Operations Platform — RC4 desk chrome.
 * Never mutates trading / AI / OMS / MT5 / Risk.
 */
export function CustomerOperationsPlatform() {
  const { user } = useAuth();
  const allowed = canAccessIteOps(user);
  const qc = useQueryClient();
  const [section, setSection] = useState<Section>("fleet");
  const [customerId, setCustomerId] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [licenseFilter, setLicenseFilter] = useState("");
  const [ticketSubject, setTicketSubject] = useState("");

  const platformQ = useQuery({
    queryKey: ["customer-ops-platform"],
    queryFn: () => customerOpsApi.platform(),
    enabled: allowed,
    refetchInterval: 15_000,
    retry: false,
  });

  const fleetQ = useQuery({
    queryKey: ["customer-ops-fleet", statusFilter, licenseFilter],
    queryFn: () =>
      customerOpsApi.fleet({
        status: statusFilter || undefined,
        license: licenseFilter || undefined,
      }),
    enabled: allowed && section === "fleet",
    refetchInterval: 15_000,
    retry: false,
  });

  const workspaceQ = useQuery({
    queryKey: ["customer-ops-workspace", customerId],
    queryFn: () => customerOpsApi.customer(customerId),
    enabled: allowed && section === "workspace" && customerId.length > 8,
    retry: false,
  });

  const createTicket = useMutation({
    mutationFn: () =>
      customerOpsApi.createTicket({
        subject: ticketSubject || "Support request",
        priority: "normal",
      }),
    onSuccess: () => {
      setTicketSubject("");
      void qc.invalidateQueries({ queryKey: ["customer-ops-platform"] });
    },
  });

  const licenseAction = useMutation({
    mutationFn: (p: { id: string; action: string }) =>
      customerOpsApi.licenseAction(p.id, p.action),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["customer-ops-platform"] });
    },
  });

  const data = asRecord(platformQ.data);
  const flags = asRecord(data.flags);
  const analytics = asRecord(data.analytics);
  const licenses = asRecord(data.licenses);
  const licenseRows = asList(licenses.licenses);
  const brokers = asRecord(data.brokers);
  const brokerRows = asList(brokers.connections);
  const support = asRecord(data.support);
  const tickets = asList(support.tickets);
  const notifications = asRecord(data.notifications);
  const notifRows = asList(notifications.notifications);
  const audit = asRecord(data.audit);
  const auditRows = asList(audit.items);
  const fleet = asRecord(fleetQ.data ?? data.fleet);
  const fleetRows = asList(fleet.customers);
  const workspace = asRecord(workspaceQ.data);

  const sections = useMemo(
    () =>
      [
        ["fleet", "Fleet"],
        ["licenses", "Licenses"],
        ["brokers", "Brokers"],
        ["support", "Support"],
        ["notifications", "Notifications"],
        ["analytics", "Analytics"],
        ["audit", "Audit"],
        ["workspace", "Workspace"],
      ] as const,
    [],
  );

  if (!allowed) {
    return (
      <DeskError
        message={iteOpsAccessDeniedMessage(
          user,
          undefined,
          "Customer Operations Platform",
        )}
      />
    );
  }

  if (platformQ.isLoading && !platformQ.data) {
    return <DeskSkeleton rows={12} />;
  }

  if (platformQ.error && !platformQ.data) {
    return (
      <DeskError
        message={iteOpsAccessDeniedMessage(
          user,
          platformQ.error,
          "Customer Operations Platform",
        )}
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="neutral">COP v1</Badge>
        <Badge tone="success">
          trading untouched · {fmt(flags.modifies_trading, "false")}
        </Badge>
        <Badge tone="success">
          secrets · {fmt(flags.credentials_exposed, "false")}
        </Badge>
        <Button asChild size="sm" variant="outline">
          <Link href="/admin/noc">NOC</Link>
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

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <NocPanel title="Active customers">
          <p className="font-mono text-lg">{fmt(analytics.active_customers, "0")}</p>
        </NocPanel>
        <NocPanel title="Connected brokers">
          <p className="font-mono text-lg">{fmt(analytics.connected_brokers, "0")}</p>
        </NocPanel>
        <NocPanel title="Support pending">
          <p className="font-mono text-lg">
            {fmt(asRecord(analytics.support_metrics).pending, "0")}
          </p>
        </NocPanel>
        <NocPanel title="Licenses active">
          <p className="font-mono text-lg">
            {fmt(asRecord(analytics.license_metrics).active, "0")}
          </p>
        </NocPanel>
      </div>

      {section === "fleet" ? (
        <NocPanel
          title="Customer Fleet"
          action={
            <div className="flex gap-2">
              <input
                className="border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-[11px]"
                placeholder="Status filter"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
              />
              <input
                className="border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-[11px]"
                placeholder="License filter"
                value={licenseFilter}
                onChange={(e) => setLicenseFilter(e.target.value)}
              />
            </div>
          }
        >
          {fleetRows.length === 0 ? (
            <DeskEmpty
              icon={Building2}
              title="No customers in filter"
              description="Production users appear when available. Never fabricated."
            />
          ) : (
            <DeskTable
              columns={[
                "Customer",
                "Status",
                "License",
                "MT5",
                "Robot",
                "Gateway",
                "Health",
              ]}
              rows={fleetRows.slice(0, 40).map((row) => {
                const r = asRecord(row);
                return [
                  fmt(r.email || r.display_name || r.customer_id),
                  fmt(r.status),
                  fmt(r.license),
                  fmt(r.mt5),
                  fmt(r.robot_online),
                  fmt(r.gateway),
                  fmt(r.health),
                ];
              })}
            />
          )}
        </NocPanel>
      ) : null}

      {section === "licenses" ? (
        <NocPanel title="License Center" action={<Badge tone="neutral">auditable</Badge>}>
          {licenseRows.length === 0 ? (
            <p className="text-[12px] text-[var(--fg-muted)]">
              No licenses in production yet. Pending approvals appear when
              created via existing licensing workflow.
            </p>
          ) : (
            <DeskTable
              columns={["ID", "User", "Tier", "Status", "Actions"]}
              rows={licenseRows.slice(0, 40).map((row) => {
                const r = asRecord(row);
                const id = str(r.id);
                return [
                  id.slice(0, 8),
                  fmt(r.user_id).slice(0, 8),
                  fmt(r.tier),
                  fmt(r.status),
                  <span key={id} className="flex gap-1">
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={licenseAction.isPending}
                      onClick={() =>
                        licenseAction.mutate({ id, action: "activate" })
                      }
                    >
                      Approve
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={licenseAction.isPending}
                      onClick={() =>
                        licenseAction.mutate({ id, action: "suspend" })
                      }
                    >
                      Suspend
                    </Button>
                  </span>,
                ];
              })}
            />
          )}
          <NocRow
            label="Modifies licensing rules"
            value={fmt(licenses.modifies_licensing_rules, "false")}
            tone="ok"
          />
        </NocPanel>
      ) : null}

      {section === "brokers" ? (
        <NocPanel
          title="Broker Connection Center"
          action={
            <Badge tone="success">
              credentials · {fmt(brokers.credentials_exposed, "false")}
            </Badge>
          }
        >
          {brokerRows.length === 0 ? (
            <p className="text-[12px] text-[var(--fg-muted)]">
              No MT5 connections in production snapshot.
            </p>
          ) : (
            <DeskTable
              columns={[
                "Broker",
                "Server",
                "Login",
                "Health",
                "Latency",
                "Heartbeat",
              ]}
              rows={brokerRows.slice(0, 40).map((row) => {
                const r = asRecord(row);
                return [
                  fmt(r.broker),
                  fmt(r.server),
                  fmt(r.login),
                  fmt(r.connection_health),
                  fmt(r.latency_ms),
                  fmt(r.last_heartbeat),
                ];
              })}
            />
          )}
        </NocPanel>
      ) : null}

      {section === "support" ? (
        <NocPanel title="Support Center">
          <div className="mb-3 flex flex-wrap gap-2">
            <input
              className="min-w-[220px] flex-1 border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5 text-[12px]"
              placeholder="New ticket subject"
              value={ticketSubject}
              onChange={(e) => setTicketSubject(e.target.value)}
            />
            <Button
              size="sm"
              disabled={createTicket.isPending}
              onClick={() => createTicket.mutate()}
            >
              Create request
            </Button>
          </div>
          {tickets.length === 0 ? (
            <p className="text-[12px] text-[var(--fg-muted)]">
              No support requests yet.
            </p>
          ) : (
            <DeskTable
              columns={["ID", "Subject", "Priority", "Status", "Assigned"]}
              rows={tickets.slice(0, 40).map((row) => {
                const r = asRecord(row);
                return [
                  fmt(r.id).slice(0, 10),
                  fmt(r.subject),
                  fmt(r.priority),
                  fmt(r.status),
                  fmt(r.assigned_staff),
                ];
              })}
            />
          )}
        </NocPanel>
      ) : null}

      {section === "notifications" ? (
        <NocPanel title="Institutional Notifications">
          <NocRow
            label="Channels"
            value={fmt(
              Array.isArray(notifications.channels)
                ? notifications.channels.join(" · ")
                : "customer · operator · system · gateway · trading · security",
            )}
          />
          {notifRows.length === 0 ? (
            <p className="mt-2 text-[12px] text-[var(--fg-muted)]">
              No COP notifications published.
            </p>
          ) : (
            <DeskTable
              columns={["Channel", "Title", "Severity", "At"]}
              rows={notifRows.slice(0, 40).map((row) => {
                const r = asRecord(row);
                return [
                  fmt(r.channel),
                  fmt(r.title),
                  fmt(r.severity),
                  fmt(r.created_at),
                ];
              })}
            />
          )}
        </NocPanel>
      ) : null}

      {section === "analytics" ? (
        <NocPanel title="Enterprise Analytics">
          <NocRow label="Active customers" value={fmt(analytics.active_customers, "0")} />
          <NocRow label="Active robots" value={fmt(analytics.active_robots, "0")} />
          <NocRow
            label="Connected brokers"
            value={fmt(analytics.connected_brokers, "0")}
          />
          <NocRow
            label="Countries"
            value={fmt(analytics.countries_count, "0")}
          />
          <NocRow
            label="Revenue"
            value={fmt(analytics.revenue, "not fabricated")}
          />
          <NocRow
            label="Fabricated"
            value={fmt(analytics.fabricated, "false")}
            tone="ok"
          />
        </NocPanel>
      ) : null}

      {section === "audit" ? (
        <NocPanel title="Enterprise Audit" action={<Badge tone="neutral">immutable</Badge>}>
          {auditRows.length === 0 ? (
            <p className="text-[12px] text-[var(--fg-muted)]">
              Administrative actions append here (operator · action · target ·
              before/after · IP).
            </p>
          ) : (
            <DeskTable
              columns={["Time", "Operator", "Action", "Target", "IP"]}
              rows={auditRows.slice(0, 50).map((row) => {
                const r = asRecord(row);
                return [
                  fmt(r.timestamp),
                  fmt(r.operator),
                  fmt(r.action),
                  fmt(r.target).slice(0, 12),
                  fmt(r.ip),
                ];
              })}
            />
          )}
        </NocPanel>
      ) : null}

      {section === "workspace" ? (
        <NocPanel title="Customer Workspace">
          <div className="mb-3 flex gap-2">
            <input
              className="min-w-[260px] flex-1 border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5 font-mono text-[12px]"
              placeholder="Customer UUID"
              value={customerId}
              onChange={(e) => setCustomerId(e.target.value.trim())}
            />
          </div>
          {!customerId ? (
            <p className="text-[12px] text-[var(--fg-muted)]">
              Enter a production customer id to load profile, license, robot,
              broker/MT5, activity, devices, logins, support, notifications.
            </p>
          ) : workspaceQ.isLoading ? (
            <DeskSkeleton rows={6} />
          ) : (
            <>
              <NocRow
                label="Profile"
                value={fmt(
                  asRecord(workspace.profile).email ||
                    asRecord(workspace.profile).display_name,
                )}
              />
              <NocRow label="License" value={fmt(workspace.license_status)} />
              <NocRow label="Robot" value={fmt(workspace.robot_status)} />
              <NocRow label="Broker" value={fmt(workspace.broker_status)} />
              <NocRow
                label="MT5"
                value={fmt(asRecord(workspace.mt5_connection).status)}
              />
              <NocRow
                label="Support requests"
                value={fmt(asList(workspace.support_requests).length, "0")}
              />
              <NocRow
                label="Credentials exposed"
                value={fmt(workspace.credentials_exposed, "false")}
                tone="ok"
              />
            </>
          )}
        </NocPanel>
      ) : null}
    </div>
  );
}
