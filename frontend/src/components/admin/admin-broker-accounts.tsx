"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { ReasonDialog } from "@/components/admin/reason-dialog";
import { adminManageApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, str } from "@/lib/desk";
import { ACTION_COPY, brokerActions, brokerStatusTone, formatDate } from "@/lib/admin/admin-format";

type Pending = { id: string; action: "disable" | "enable" | "remove"; label: string };

/** Every customer broker account, with disconnect / enable / remove. */
export function AdminBrokerAccounts() {
  const qc = useQueryClient();
  const [showRemoved, setShowRemoved] = useState(false);
  const [query, setQuery] = useState("");
  const [pending, setPending] = useState<Pending | null>(null);

  const q = useQuery({
    queryKey: ["admin-manage-brokers", showRemoved],
    queryFn: () => adminManageApi.brokers(showRemoved),
    refetchInterval: 30_000,
    retry: false,
  });
  const rows = useMemo(() => asList(asRecord(q.data).brokers).map(asRecord), [q.data]);
  const filtered = useMemo(() => {
    const s = query.trim().toLowerCase();
    if (!s) return rows;
    return rows.filter((r) =>
      [r.email, r.broker, r.account, r.server].some((v) => str(v, "").toLowerCase().includes(s)),
    );
  }, [rows, query]);

  const m = useMutation({
    mutationFn: ({ p, reason }: { p: Pending; reason: string }) =>
      adminManageApi.brokerAction(p.id, { action: p.action, reason }),
    onSuccess: async () => {
      toast.success("Broker updated");
      setPending(null);
      await qc.invalidateQueries({ queryKey: ["admin-manage-brokers"] });
    },
    onError: (e) => {
      const d = e instanceof ApiError ? asRecord(asRecord(e.details).detail) : {};
      toast.error(str(d.message, "") || (e instanceof Error ? e.message : "Could not update the broker."));
    },
  });

  return (
    <section className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface-2)] p-4">
      <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-sm font-semibold">Broker accounts</h2>
          <p className="text-xs text-[var(--fg-muted)]">
            Disconnect stops the robot on that account and frees its terminal. Remove also deletes the stored password.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--fg-subtle)]" />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search"
              className="h-9 w-44 pl-8"
              aria-label="Search broker accounts"
            />
          </div>
          <label className="flex items-center gap-1.5 text-xs text-[var(--fg-muted)]">
            <input type="checkbox" checked={showRemoved} onChange={(e) => setShowRemoved(e.target.checked)} />
            Show removed
          </label>
        </div>
      </div>
      {q.isLoading ? (
        <DeskSkeleton rows={4} />
      ) : q.isError ? (
        <DeskError message="Broker accounts could not be loaded." onRetry={() => q.refetch()} />
      ) : filtered.length === 0 ? (
        <p className="py-6 text-center text-sm text-[var(--fg-muted)]">No broker accounts.</p>
      ) : (
        <ul className="divide-y divide-[var(--border)]">
          {filtered.map((b) => {
            const status = str(b.status);
            return (
              <li key={str(b.id)} className="flex flex-col gap-2 py-3 md:flex-row md:items-center md:justify-between">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">
                    {str(b.broker) || "Broker"} · {str(b.account)}{" "}
                    <span className="text-[var(--fg-muted)]">({str(b.environment)})</span>
                  </p>
                  <p className="truncate text-xs text-[var(--fg-muted)]">
                    <Link className="hover:underline" href={`/admin/users/${encodeURIComponent(str(b.user_id))}`}>
                      {str(b.email)}
                    </Link>{" "}
                    · {str(b.server)} · robot {str(b.robot_state).toLowerCase()} · updated {formatDate(str(b.updated_at, ""))}
                  </p>
                  {str(b.admin_note) ? (
                    <p className="text-xs text-[var(--warning)]">Admin note: {str(b.admin_note)}</p>
                  ) : null}
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={brokerStatusTone(status)}>{status}</Badge>
                  {str(b.verification) ? <Badge tone="neutral">{str(b.verification)}</Badge> : null}
                  {brokerActions(status).map((a) => (
                    <Button
                      key={a}
                      size="sm"
                      variant={a === "remove" ? "danger" : a === "enable" ? "default" : "secondary"}
                      onClick={() =>
                        setPending({ id: str(b.id), action: a, label: `${str(b.broker)} ${str(b.account)}` })
                      }
                    >
                      {a === "disable" ? "Disconnect" : a === "enable" ? "Enable" : "Remove"}
                    </Button>
                  ))}
                </div>
              </li>
            );
          })}
        </ul>
      )}
      {pending ? (
        <ReasonDialog
          open
          title={ACTION_COPY[pending.action].title}
          body={`${pending.label}. ${ACTION_COPY[pending.action].body}`}
          confirmLabel={ACTION_COPY[pending.action].confirm}
          danger={ACTION_COPY[pending.action].danger}
          pending={m.isPending}
          onCancel={() => setPending(null)}
          onConfirm={(reason) => m.mutate({ p: pending, reason })}
        />
      ) : null}
    </section>
  );
}
