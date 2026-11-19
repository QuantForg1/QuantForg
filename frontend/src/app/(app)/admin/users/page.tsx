"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ChevronRight, Search, ShieldOff, Users } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { adminManageApi } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { formatDate, subscriptionTone, userStatusTone } from "@/lib/admin/admin-format";
import { useAuth } from "@/providers/auth-provider";
import { canAccessIteOps, iteOpsAccessDeniedMessage } from "@/lib/auth/ite-ops-access";
import { cn } from "@/lib/utils";

const STATUS_FILTERS = [
  { id: "", label: "All" },
  { id: "active", label: "Active" },
  { id: "pending", label: "Pending" },
  { id: "suspended", label: "Suspended" },
  { id: "deactivated", label: "Deactivated" },
];

export default function AdminUsersPage() {
  const { user } = useAuth();
  const allowed = canAccessIteOps(user);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");

  const usersQ = useQuery({
    queryKey: ["admin-manage-users", status],
    queryFn: () => adminManageApi.users({ status: status || undefined }),
    enabled: allowed,
    refetchInterval: 30_000,
    retry: false,
  });

  const data = asRecord(usersQ.data);
  const rows = useMemo(() => asList(data.users).map(asRecord), [data.users]);
  const byStatus = asRecord(data.by_status);
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter(
      (r) =>
        str(r.email, "").toLowerCase().includes(q) ||
        str(r.display_name, "").toLowerCase().includes(q),
    );
  }, [rows, query]);

  const header = (
    <PageHeader
      eyebrow="Admin Portal"
      title="Users"
      description="Search customers, review their subscription and brokers, and manage access. Every change is recorded in the audit log."
    />
  );

  if (!allowed) {
    return (
      <div className="min-w-0 space-y-4">
        {header}
        <DeskError message={iteOpsAccessDeniedMessage(user, undefined, "User Management")} />
      </div>
    );
  }

  return (
    <div className="min-w-0 space-y-4">
      {header}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {(["active", "pending", "suspended", "deactivated"] as const).map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => setStatus(status === s ? "" : s)}
            className={cn(
              "rounded-[var(--radius-os)] border bg-[var(--surface-2)] px-4 py-3 text-left transition-colors",
              status === s ? "border-[var(--accent)]" : "border-[var(--border)] hover:border-[var(--border-strong)]",
            )}
          >
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">{s}</p>
            <p className="mt-1 text-2xl font-semibold tabular-nums">{num(byStatus[s]) || 0}</p>
          </button>
        ))}
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--fg-subtle)]" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by email or name"
            className="pl-9"
            aria-label="Search users"
          />
        </div>
        <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Filter by status">
          {STATUS_FILTERS.map((f) => (
            <button
              key={f.id || "all"}
              type="button"
              role="tab"
              aria-selected={status === f.id}
              onClick={() => setStatus(f.id)}
              className={cn(
                "rounded-full border px-3 py-1.5 text-xs font-medium",
                status === f.id
                  ? "border-[var(--accent)] bg-[color-mix(in_srgb,var(--accent)_14%,transparent)] text-[var(--fg)]"
                  : "border-[var(--border)] text-[var(--fg-muted)] hover:text-[var(--fg)]",
              )}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {usersQ.isLoading ? (
        <DeskSkeleton rows={8} />
      ) : usersQ.isError ? (
        <DeskError message="Users could not be loaded." onRetry={() => usersQ.refetch()} />
      ) : filtered.length === 0 ? (
        <DeskEmpty icon={Users} title="No users match" description="Change the search or the status filter." />
      ) : (
        <div className="overflow-hidden rounded-[var(--radius-os)] border border-[var(--border)]">
          <div className="hidden grid-cols-[2fr_1fr_1fr_0.7fr_1.2fr_24px] gap-3 border-b border-[var(--border)] bg-[var(--surface-2)] px-4 py-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)] md:grid">
            <span>User</span>
            <span>Status</span>
            <span>Subscription</span>
            <span>Brokers</span>
            <span>Last sign-in</span>
            <span />
          </div>
          <ul className="divide-y divide-[var(--border)]">
            {filtered.map((r) => {
              const id = str(r.id);
              const st = str(r.status);
              const sub = str(r.subscription, "none");
              return (
                <li key={id}>
                  <Link
                    href={`/admin/users/${encodeURIComponent(id)}`}
                    className="grid grid-cols-[1fr_auto] items-center gap-3 px-4 py-3 hover:bg-[var(--surface-2)] md:grid-cols-[2fr_1fr_1fr_0.7fr_1.2fr_24px]"
                  >
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-medium">{str(r.email)}</span>
                      <span className="flex items-center gap-1.5 truncate text-xs text-[var(--fg-muted)]">
                        {str(r.display_name) || "—"}
                        {str(r.role) !== "trader" ? <Badge tone="accent">{str(r.role)}</Badge> : null}
                        {num(r.restrictions) > 0 ? (
                          <span className="inline-flex items-center gap-0.5 text-[var(--warning)]">
                            <ShieldOff className="h-3 w-3" /> {num(r.restrictions)} restricted
                          </span>
                        ) : null}
                      </span>
                      <span className="mt-1 flex flex-wrap gap-1.5 md:hidden">
                        <Badge tone={userStatusTone(st)}>{st}</Badge>
                        <Badge tone={subscriptionTone(sub)}>{sub}</Badge>
                      </span>
                    </span>
                    <span className="hidden md:block">
                      <Badge tone={userStatusTone(st)}>{st}</Badge>
                    </span>
                    <span className="hidden md:block">
                      <Badge tone={subscriptionTone(sub)}>{sub}</Badge>
                    </span>
                    <span className="hidden text-sm tabular-nums md:block">{num(r.brokers) || 0}</span>
                    <span className="hidden text-xs text-[var(--fg-muted)] md:block">{formatDate(str(r.last_login_at, ""))}</span>
                    <ChevronRight className="h-4 w-4 text-[var(--fg-subtle)]" />
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      )}
      {filtered.length > 0 ? (
        <p className="text-xs text-[var(--fg-subtle)]">
          Showing {filtered.length} of {num(data.count) || rows.length} users.
        </p>
      ) : null}
    </div>
  );
}
