"use client";

import { useMemo } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, UserCircle } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DeskEmpty,
  DeskError,
  DeskSkeleton,
  DeskTable,
} from "@/components/desk/primitives";
import { NocPanel, NocRow } from "@/components/ops/noc/noc-primitives";
import { customerOpsApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { useAuth } from "@/providers/auth-provider";
import {
  canAccessIteOps,
  iteOpsAccessDeniedMessage,
} from "@/lib/auth/ite-ops-access";

const LICENSE_ACTIONS = ["activate", "suspend", "revoke"] as const;
type LicenseAction = (typeof LICENSE_ACTIONS)[number];

const SENSITIVE_KEY =
  /password|secret|token|credential|hash|api_key|private_key/i;

function fmt(v: unknown, fallback = "—"): string {
  if (v === null || v === undefined || v === "") return fallback;
  if (typeof v === "boolean") return v ? "yes" : "no";
  return String(v);
}

function safeBrokerRow(row: Record<string, unknown>): string[] {
  const redacted: Record<string, unknown> = {};
  for (const [key, val] of Object.entries(row)) {
    if (SENSITIVE_KEY.test(key)) continue;
    if (key === "login" && !("login_masked" in row)) {
      redacted.login_masked = "redacted";
      continue;
    }
    redacted[key] = val;
  }
  return [
    fmt(redacted.server ?? redacted.broker),
    fmt(redacted.login_masked ?? redacted.login),
    fmt(redacted.status ?? redacted.connection_health),
    fmt(redacted.last_heartbeat ?? redacted.last_heartbeat_at),
    fmt(redacted.latency_ms),
  ];
}

function confirmLicenseAction(action: LicenseAction, tier: string): boolean {
  const labels: Record<LicenseAction, string> = {
    activate: "activate",
    suspend: "suspend",
    revoke: "revoke",
  };
  return window.confirm(
    `Confirm ${labels[action]} license${tier ? ` (${tier})` : ""}? This calls customer-ops licenseAction and is audited.`,
  );
}

export default function AdminUserDetailPage() {
  const params = useParams();
  const customerId = decodeURIComponent(str(params?.id, ""));
  const { user } = useAuth();
  const allowed = canAccessIteOps(user);
  const qc = useQueryClient();

  const workspaceQ = useQuery({
    queryKey: ["admin-user-workspace", customerId],
    queryFn: () => customerOpsApi.customer(customerId),
    enabled: allowed && customerId.length > 0,
    refetchInterval: 15_000,
    retry: false,
  });

  const licenseAction = useMutation({
    mutationFn: (p: { id: string; action: LicenseAction; reason?: string }) =>
      customerOpsApi.licenseAction(p.id, p.action, p.reason ?? ""),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["admin-user-workspace", customerId] });
      void qc.invalidateQueries({ queryKey: ["admin-users-fleet"] });
      void qc.invalidateQueries({ queryKey: ["customer-ops-platform"] });
    },
  });

  const workspace = asRecord(workspaceQ.data);
  const profile = asRecord(workspace.profile);
  const licenses = asList(workspace.licenses).map(asRecord);
  const mt5Connections = asList(workspace.mt5_connections).map(asRecord);
  const supportTickets = asList(workspace.support_requests).map(asRecord);
  const loginHistory = asList(workspace.login_history).map(asRecord);
  const latestActivity = asList(workspace.latest_activity).map(asRecord);
  const activityRows = useMemo(
    () => (loginHistory.length > 0 ? loginHistory : latestActivity),
    [loginHistory, latestActivity],
  );

  const titleEmail = fmt(profile.email || profile.display_name, customerId);

  if (!allowed) {
    return (
      <div className="min-w-0 space-y-4">
        <PageHeader eyebrow="Admin Portal" title="User CRM" description="Customer workspace." />
        <DeskError
          message={iteOpsAccessDeniedMessage(user, undefined, "User CRM")}
        />
      </div>
    );
  }

  if (!customerId) {
    return (
      <div className="min-w-0 space-y-4">
        <PageHeader eyebrow="Admin Portal" title="User CRM" description="Missing customer id." />
        <DeskEmpty
          icon={UserCircle}
          title="No customer selected"
          description="Open a user from User Management."
          actionLabel="Back to users"
          actionHref="/admin/users"
        />
      </div>
    );
  }

  if (workspaceQ.isLoading && !workspaceQ.data) {
    return (
      <div className="min-w-0 space-y-4">
        <PageHeader
          eyebrow="Admin Portal"
          title={titleEmail}
          description={`Customer ${customerId.slice(0, 8)}…`}
        />
        <DeskSkeleton rows={14} />
      </div>
    );
  }

  if (workspaceQ.error && !workspaceQ.data) {
    return (
      <div className="min-w-0 space-y-4">
        <PageHeader eyebrow="Admin Portal" title="User CRM" description={customerId} />
        <DeskError
          message={iteOpsAccessDeniedMessage(user, workspaceQ.error, "User CRM")}
        />
      </div>
    );
  }

  return (
    <div className="min-w-0 space-y-4">
      <PageHeader
        eyebrow="Admin Portal"
        title={titleEmail}
        description="Production customer workspace — licenses, brokers (redacted), support, and login history."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="outline">
              <Link href="/admin/users">
                <ArrowLeft className="mr-1 h-3.5 w-3.5" />
                Users
              </Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/admin/support">Support desk</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href={`/admin/customer-ops#workspace`}>COP workspace</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="neutral">ID {customerId.slice(0, 12)}…</Badge>
            <Badge tone="neutral">License {fmt(workspace.license_status)}</Badge>
            <Badge tone="success">
              credentials · {fmt(workspace.credentials_exposed, "false")}
            </Badge>
          </div>

          <NocPanel title="Profile">
            <NocRow label="Email" value={fmt(profile.email)} />
            <NocRow label="Display name" value={fmt(profile.display_name)} />
            <NocRow label="Status" value={fmt(profile.status)} />
            <NocRow label="Role" value={fmt(profile.role)} />
            <NocRow label="Last login" value={fmt(profile.last_login_at)} />
            <NocRow label="Created" value={fmt(profile.created_at)} />
            <NocRow label="Country" value={fmt(profile.country)} />
          </NocPanel>

          <NocPanel
            title="Licenses"
            action={<Badge tone="neutral">licenseAction API</Badge>}
          >
            {licenses.length === 0 ? (
              <p className="text-[12px] text-[var(--fg-muted)]">
                No license records for this customer in production.
              </p>
            ) : (
              <DeskTable
                columns={["Tier", "Status", "Issued", "Expires", "Actions"]}
                rows={licenses.map((lic) => {
                  const lid = str(lic.id, "");
                  const tier = fmt(lic.tier);
                  return [
                    tier,
                    fmt(lic.status),
                    fmt(lic.issued_at),
                    fmt(lic.expires_at),
                    <span key={lid} className="flex flex-wrap gap-1">
                      {LICENSE_ACTIONS.map((action) => (
                        <Button
                          key={`${lid}-${action}`}
                          type="button"
                          size="sm"
                          variant="outline"
                          disabled={licenseAction.isPending || !lid}
                          onClick={() => {
                            if (!confirmLicenseAction(action, tier)) return;
                            licenseAction.mutate({ id: lid, action });
                          }}
                        >
                          {action}
                        </Button>
                      ))}
                    </span>,
                  ];
                })}
              />
            )}
          </NocPanel>

          <NocPanel title="Brokers & MT5" action={<Badge tone="success">redacted</Badge>}>
            {mt5Connections.length === 0 ? (
              <p className="text-[12px] text-[var(--fg-muted)]">
                No MT5 connections in production snapshot for this user.
              </p>
            ) : (
              <DeskTable
                columns={[
                  "Server",
                  "Login",
                  "Status",
                  "Heartbeat",
                  "Latency ms",
                ]}
                rows={mt5Connections.map((row) => safeBrokerRow(row))}
              />
            )}
            <NocRow label="Broker status" value={fmt(workspace.broker_status)} />
            <NocRow
              label="Primary MT5"
              value={fmt(asRecord(workspace.mt5_connection).status)}
            />
          </NocPanel>

          <NocPanel title="Support requests">
            {supportTickets.length === 0 ? (
              <p className="text-[12px] text-[var(--fg-muted)]">
                No tickets linked to this customer.
              </p>
            ) : (
              <DeskTable
                columns={["ID", "Subject", "Priority", "Status", "Updated"]}
                rows={supportTickets.map((t) => [
                  fmt(t.id).slice(0, 12),
                  fmt(t.subject),
                  fmt(t.priority),
                  fmt(t.status),
                  fmt(t.updated_at ?? t.created_at),
                ])}
              />
            )}
          </NocPanel>

          <NocPanel title="Activity & login history">
            {activityRows.length === 0 ? (
              <p className="text-[12px] text-[var(--fg-muted)]">
                No login or activity events recorded yet.
              </p>
            ) : (
              <DeskTable
                columns={["Time", "Event", "IP", "Detail"]}
                rows={activityRows.slice(0, 40).map((row) => [
                  fmt(row.timestamp ?? row.at ?? row.created_at),
                  fmt(row.event ?? row.action ?? row.type ?? "login"),
                  fmt(row.ip ?? row.ip_address),
                  fmt(row.detail ?? row.user_agent ?? row.message),
                ])}
              />
            )}
          </NocPanel>
        </div>
      </PageMotion>
    </div>
  );
}
