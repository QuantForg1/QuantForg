"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Users } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
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
import { NocPanel } from "@/components/ops/noc/noc-primitives";
import { customerOpsApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { useAuth } from "@/providers/auth-provider";
import {
  canAccessIteOps,
  iteOpsAccessDeniedMessage,
} from "@/lib/auth/ite-ops-access";

const PAGE_SIZE = 25;

function fmt(v: unknown, fallback = "—"): string {
  if (v === null || v === undefined || v === "") return fallback;
  return String(v);
}

function brokersCount(row: Record<string, unknown>): string {
  const explicit =
    row.brokers_count ?? row.broker_count ?? row.connections_count;
  if (typeof explicit === "number" && Number.isFinite(explicit)) {
    return String(explicit);
  }
  const conns = row.mt5_connections ?? row.brokers ?? row.connections;
  if (Array.isArray(conns)) return String(conns.length);
  return "—";
}

function createdAt(row: Record<string, unknown>): string {
  const v =
    row.created_at ?? row.registered_at ?? asRecord(row.profile).created_at;
  return fmt(v, "—");
}

export default function AdminUsersPage() {
  const { user } = useAuth();
  const allowed = canAccessIteOps(user);
  const [statusFilter, setStatusFilter] = useState("");
  const [licenseFilter, setLicenseFilter] = useState("");
  const [emailQuery, setEmailQuery] = useState("");
  const [page, setPage] = useState(0);

  const fleetQ = useQuery({
    queryKey: ["admin-users-fleet", statusFilter, licenseFilter],
    queryFn: () =>
      customerOpsApi.fleet({
        status: statusFilter.trim() || undefined,
        license: licenseFilter.trim() || undefined,
      }),
    enabled: allowed,
    refetchInterval: 15_000,
    retry: false,
  });

  const fleetRoot = asRecord(fleetQ.data);
  const fleetRows = useMemo(
    () => asList(fleetRoot.customers).map(asRecord),
    [fleetQ.data],
  );

  const filtered = useMemo(() => {
    const q = emailQuery.trim().toLowerCase();
    if (!q) return fleetRows;
    return fleetRows.filter((r) => {
      const email = fmt(r.email, "").toLowerCase();
      const name = fmt(r.display_name, "").toLowerCase();
      const id = fmt(r.customer_id, "").toLowerCase();
      return email.includes(q) || name.includes(q) || id.includes(q);
    });
  }, [fleetRows, emailQuery]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount - 1);
  const pageRows = filtered.slice(
    safePage * PAGE_SIZE,
    safePage * PAGE_SIZE + PAGE_SIZE,
  );

  if (!allowed) {
    return (
      <div className="min-w-0 space-y-4">
        <PageHeader
          eyebrow="Admin Portal"
          title="User Management"
          description="Production customer fleet — search, filter, and open CRM workspace."
        />
        <DeskError
          message={iteOpsAccessDeniedMessage(user, undefined, "User Management")}
        />
      </div>
    );
  }

  if (fleetQ.isLoading && !fleetQ.data) {
    return (
      <div className="min-w-0 space-y-4">
        <PageHeader
          eyebrow="Admin Portal"
          title="User Management"
          description="Production customer fleet — search, filter, and open CRM workspace."
        />
        <DeskSkeleton rows={12} />
      </div>
    );
  }

  if (fleetQ.error && !fleetQ.data) {
    return (
      <div className="min-w-0 space-y-4">
        <PageHeader
          eyebrow="Admin Portal"
          title="User Management"
          description="Production customer fleet — search, filter, and open CRM workspace."
        />
        <DeskError
          message={iteOpsAccessDeniedMessage(
            user,
            fleetQ.error,
            "User Management",
          )}
        />
      </div>
    );
  }

  return (
    <div className="min-w-0 space-y-4">
      <PageHeader
        eyebrow="Admin Portal"
        title="User Management"
        description="Institutional user CRM — fleet data from Customer Operations. Never fabricates accounts."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="outline">
              <Link href="/admin/customer-ops#fleet">COP fleet tab</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/admin/support">Support desk</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="neutral">{fmt(fleetRoot.count, "0")} matched</Badge>
            <Badge tone="neutral">
              {fmt(fleetRoot.total_unfiltered, String(filtered.length))} total
            </Badge>
          </div>

          <NocPanel
            title="Users"
            action={
              <div className="flex flex-wrap gap-2">
                <input
                  className="min-w-[180px] border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-[11px]"
                  placeholder="Search email / name / id"
                  value={emailQuery}
                  onChange={(e) => {
                    setEmailQuery(e.target.value);
                    setPage(0);
                  }}
                />
                <input
                  className="w-[120px] border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-[11px]"
                  placeholder="Status"
                  value={statusFilter}
                  onChange={(e) => {
                    setStatusFilter(e.target.value);
                    setPage(0);
                  }}
                />
                <input
                  className="w-[120px] border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-[11px]"
                  placeholder="License"
                  value={licenseFilter}
                  onChange={(e) => {
                    setLicenseFilter(e.target.value);
                    setPage(0);
                  }}
                />
              </div>
            }
          >
            {filtered.length === 0 ? (
              <DeskEmpty
                icon={Users}
                title="No users match"
                description="Adjust filters or wait for production users. Data comes from customer-ops fleet only."
              />
            ) : (
              <>
                <DeskTable
                  columns={[
                    "Email",
                    "Status",
                    "License",
                    "Brokers",
                    "Created",
                    "",
                  ]}
                  rows={pageRows.map((r) => {
                    const id = str(r.customer_id, "");
                    const label = fmt(r.email || r.display_name || id);
                    return [
                      <Link
                        key={`email-${id}`}
                        href={`/admin/users/${encodeURIComponent(id)}`}
                        className="text-[var(--accent)] hover:underline"
                      >
                        {label}
                      </Link>,
                      fmt(r.status),
                      fmt(r.license),
                      brokersCount(r),
                      createdAt(r),
                      <Button key={`open-${id}`} asChild size="sm" variant="outline">
                        <Link href={`/admin/users/${encodeURIComponent(id)}`}>
                          Open
                        </Link>
                      </Button>,
                    ];
                  })}
                />
                {pageCount > 1 ? (
                  <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-[var(--border)] pt-3">
                    <p className="text-[11px] text-[var(--fg-muted)]">
                      Page {safePage + 1} of {pageCount} · {filtered.length}{" "}
                      users
                    </p>
                    <div className="flex gap-2">
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={safePage <= 0}
                        onClick={() => setPage((p) => Math.max(0, p - 1))}
                      >
                        Previous
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={safePage >= pageCount - 1}
                        onClick={() =>
                          setPage((p) => Math.min(pageCount - 1, p + 1))
                        }
                      >
                        Next
                      </Button>
                    </div>
                  </div>
                ) : null}
              </>
            )}
          </NocPanel>
        </div>
      </PageMotion>
    </div>
  );
}
