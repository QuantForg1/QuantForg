"use client";

import { useState, type ReactNode } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Pencil } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { ReasonDialog } from "@/components/admin/reason-dialog";
import { adminManageApi, customerOpsApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, str } from "@/lib/desk";
import {
  ACTION_COPY,
  brokerActions,
  brokerStatusTone,
  formatDate,
  statusActions,
  subscriptionTone,
  userStatusTone,
} from "@/lib/admin/admin-format";
import { useAuth } from "@/providers/auth-provider";
import { canAccessIteOps, iteOpsAccessDeniedMessage } from "@/lib/auth/ite-ops-access";
import { cn } from "@/lib/utils";

type Pending =
  | { kind: "status"; action: "suspend" | "reactivate" | "deactivate" }
  | { kind: "access"; feature: string; label: string; allowed: boolean }
  | { kind: "broker"; id: string; action: "disable" | "enable" | "remove" }
  | { kind: "license"; id: string; action: "activate" | "suspend" | "revoke" };

function errorText(e: unknown): string {
  if (e instanceof ApiError) {
    const d = asRecord(asRecord(e.details).detail);
    return str(d.message, "") || e.message;
  }
  return "The change could not be saved.";
}

function Section({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) {
  return (
    <section className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface-2)] p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

export default function AdminUserDetailPage() {
  const { user } = useAuth();
  const allowed = canAccessIteOps(user);
  const params = useParams<{ id: string }>();
  const id = decodeURIComponent(String(params?.id ?? ""));
  const qc = useQueryClient();
  const [pending, setPending] = useState<Pending | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [name, setName] = useState("");
  const [role, setRole] = useState("trader");
  const [editReason, setEditReason] = useState("");

  const userQ = useQuery({
    queryKey: ["admin-manage-user", id],
    queryFn: () => adminManageApi.user(id),
    enabled: allowed && Boolean(id),
    retry: false,
  });

  const refresh = async () => {
    await qc.invalidateQueries({ queryKey: ["admin-manage-user", id] });
    await qc.invalidateQueries({ queryKey: ["admin-manage-users"] });
    await qc.invalidateQueries({ queryKey: ["admin-manage-brokers"] });
  };

  const actionM = useMutation({
    mutationFn: async ({ p, reason }: { p: Pending; reason: string }) => {
      if (p.kind === "status") return adminManageApi.setStatus(id, { action: p.action, reason });
      if (p.kind === "access")
        return adminManageApi.setAccess(id, { feature: p.feature, allowed: p.allowed, reason });
      if (p.kind === "broker") return adminManageApi.brokerAction(p.id, { action: p.action, reason });
      return customerOpsApi.licenseAction(p.id, p.action, reason);
    },
    onSuccess: async () => {
      toast.success("Saved");
      setPending(null);
      await refresh();
    },
    onError: (e) => toast.error(errorText(e)),
  });

  const editM = useMutation({
    mutationFn: () => adminManageApi.updateUser(id, { display_name: name, role, reason: editReason }),
    onSuccess: async () => {
      toast.success("User updated");
      setEditOpen(false);
      setEditReason("");
      await refresh();
    },
    onError: (e) => toast.error(errorText(e)),
  });

  const back = (
    <Button asChild size="sm" variant="ghost">
      <Link href="/admin/users">
        <ArrowLeft className="h-3.5 w-3.5" /> All users
      </Link>
    </Button>
  );

  if (!allowed) {
    return (
      <div className="min-w-0 space-y-4">
        <PageHeader eyebrow="Admin Portal" title="User" />
        <DeskError message={iteOpsAccessDeniedMessage(user, undefined, "User Management")} />
      </div>
    );
  }
  if (userQ.isLoading) return <DeskSkeleton rows={10} />;
  if (userQ.isError) {
    return (
      <div className="min-w-0 space-y-4">
        {back}
        <DeskError message={errorText(userQ.error)} onRetry={() => userQ.refetch()} />
      </div>
    );
  }

  const u = asRecord(userQ.data);
  const st = str(u.status);
  const manageable = u.manageable === true;
  const access = asList(u.access).map(asRecord);
  const brokers = asList(u.brokers_list).map(asRecord);
  const licenses = asList(u.licenses).map(asRecord);
  const audit = asList(u.audit).map(asRecord);

  const dialogCopy = (() => {
    if (!pending) return null;
    if (pending.kind === "access") {
      return pending.allowed
        ? { title: `Restore ${pending.label}?`, body: "The user gets this feature back (subscription rules still apply).", confirm: "Restore access", danger: false }
        : {
            title: `Remove ${pending.label}?`,
            body:
              pending.feature === "robot_trading"
                ? "The robot stops opening new trades for this user, even with a paid plan. Open positions keep their stop loss and take profit."
                : "The user can no longer use this feature until you restore it.",
            confirm: "Remove access",
            danger: true,
          };
    }
    if (pending.kind === "license") {
      return {
        title: `${pending.action[0].toUpperCase()}${pending.action.slice(1)} this license?`,
        body: "Changes the customer's subscription license. The robot follows the license status.",
        confirm: "Confirm",
        danger: pending.action !== "activate",
      };
    }
    const c = ACTION_COPY[pending.action];
    return { title: c.title, body: c.body, confirm: c.confirm, danger: c.danger };
  })();

  return (
    <div className="min-w-0 space-y-4">
      {back}
      <PageHeader
        eyebrow="Admin Portal · User"
        title={str(u.email)}
        description={str(u.display_name) || undefined}
      />

      <Section
        title="Account"
        action={
          manageable ? (
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                setName(str(u.display_name));
                setRole(str(u.role, "trader"));
                setEditOpen(true);
              }}
            >
              <Pencil className="h-3.5 w-3.5" /> Edit
            </Button>
          ) : null
        }
      >
        <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm sm:grid-cols-4">
          <div>
            <dt className="text-xs text-[var(--fg-subtle)]">Status</dt>
            <dd className="mt-1"><Badge tone={userStatusTone(st)}>{st}</Badge></dd>
          </div>
          <div>
            <dt className="text-xs text-[var(--fg-subtle)]">Role</dt>
            <dd className="mt-1 capitalize">{str(u.role)}</dd>
          </div>
          <div>
            <dt className="text-xs text-[var(--fg-subtle)]">Subscription</dt>
            <dd className="mt-1"><Badge tone={subscriptionTone(str(u.subscription))}>{str(u.subscription, "none")}</Badge></dd>
          </div>
          <div>
            <dt className="text-xs text-[var(--fg-subtle)]">Paid until</dt>
            <dd className="mt-1">{formatDate(str(u.subscription_expires_at, ""))}</dd>
          </div>
          <div>
            <dt className="text-xs text-[var(--fg-subtle)]">Joined</dt>
            <dd className="mt-1">{formatDate(str(u.created_at, ""))}</dd>
          </div>
          <div>
            <dt className="text-xs text-[var(--fg-subtle)]">Last sign-in</dt>
            <dd className="mt-1">{formatDate(str(u.last_login_at, ""))}</dd>
          </div>
        </dl>
        {manageable ? (
          <div className="mt-4 flex flex-wrap gap-2 border-t border-[var(--border)] pt-3">
            {statusActions(st).map((a) => (
              <Button
                key={a}
                size="sm"
                variant={a === "reactivate" ? "default" : a === "deactivate" ? "danger" : "secondary"}
                onClick={() => setPending({ kind: "status", action: a })}
              >
                {ACTION_COPY[a].confirm}
              </Button>
            ))}
          </div>
        ) : (
          <p className="mt-3 text-xs text-[var(--fg-subtle)]">
            Owner and admin accounts are managed by the owner policy, not from this portal.
          </p>
        )}
      </Section>

      <Section title="Access">
        <ul className="divide-y divide-[var(--border)]">
          {access.map((a) => {
            const on = a.allowed === true;
            return (
              <li key={str(a.feature)} className="flex flex-wrap items-center justify-between gap-3 py-2.5">
                <div className="min-w-0">
                  <p className="text-sm font-medium">{str(a.label)}</p>
                  <p className="text-xs text-[var(--fg-muted)]">
                    {on ? "Allowed (subscription rules apply)" : `Removed${str(a.reason) ? ` · ${str(a.reason)}` : ""}`}
                  </p>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={on}
                  aria-label={`${str(a.label)} access`}
                  disabled={!manageable}
                  onClick={() =>
                    setPending({ kind: "access", feature: str(a.feature), label: str(a.label), allowed: !on })
                  }
                  className={cn(
                    "relative h-6 w-11 shrink-0 rounded-full transition-colors disabled:opacity-40",
                    on ? "bg-[var(--success)]" : "bg-[var(--border-strong,var(--border))]",
                  )}
                >
                  <span
                    className={cn(
                      "absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform",
                      on ? "translate-x-5" : "translate-x-0.5",
                    )}
                  />
                </button>
              </li>
            );
          })}
        </ul>
      </Section>

      <Section title={`Brokers (${brokers.length})`}>
        {brokers.length === 0 ? (
          <p className="text-sm text-[var(--fg-muted)]">No broker accounts.</p>
        ) : (
          <ul className="divide-y divide-[var(--border)]">
            {brokers.map((b) => (
              <li key={str(b.id)} className="flex flex-wrap items-center justify-between gap-3 py-2.5">
                <div className="min-w-0">
                  <p className="text-sm font-medium">
                    {str(b.broker) || "Broker"} · {str(b.account)}
                  </p>
                  <p className="text-xs text-[var(--fg-muted)]">
                    {str(b.server)} · {str(b.environment)} · robot {str(b.robot_state).toLowerCase()}
                    {str(b.verification) ? ` · ${str(b.verification)}` : ""}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={brokerStatusTone(str(b.status))}>{str(b.status)}</Badge>
                  {manageable
                    ? brokerActions(str(b.status)).map((a) => (
                        <Button
                          key={a}
                          size="sm"
                          variant={a === "remove" ? "danger" : a === "enable" ? "default" : "secondary"}
                          onClick={() => setPending({ kind: "broker", id: str(b.id), action: a })}
                        >
                          {a === "disable" ? "Disconnect" : a === "enable" ? "Enable" : "Remove"}
                        </Button>
                      ))
                    : null}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Subscription licenses">
        {licenses.length === 0 ? (
          <p className="text-sm text-[var(--fg-muted)]">No licenses. The user has not paid yet.</p>
        ) : (
          <ul className="divide-y divide-[var(--border)]">
            {licenses.map((l) => (
              <li key={str(l.id)} className="flex flex-wrap items-center justify-between gap-3 py-2.5">
                <div>
                  <p className="text-sm font-medium capitalize">{str(l.plan, "plan")}</p>
                  <p className="text-xs text-[var(--fg-muted)]">
                    Created {formatDate(str(l.created_at, ""))} · expires {formatDate(str(l.expires_at, ""))}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={subscriptionTone(str(l.status))}>{str(l.status)}</Badge>
                  {manageable
                    ? (["activate", "suspend", "revoke"] as const)
                        .filter((a) => !(a === "activate" && str(l.status) === "active"))
                        .map((a) => (
                          <Button
                            key={a}
                            size="sm"
                            variant={a === "revoke" ? "danger" : "secondary"}
                            onClick={() => setPending({ kind: "license", id: str(l.id), action: a })}
                          >
                            {a[0].toUpperCase() + a.slice(1)}
                          </Button>
                        ))
                    : null}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Admin history">
        {audit.length === 0 ? (
          <p className="text-sm text-[var(--fg-muted)]">No admin changes yet.</p>
        ) : (
          <ul className="space-y-2">
            {audit.map((a, i) => (
              <li key={i} className="text-sm">
                <span className="text-[var(--fg)]">{str(a.message)}</span>
                <span className="block text-xs text-[var(--fg-subtle)]">
                  {formatDate(str(a.at, ""))} · {str(a.actor)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Section>

      {pending && dialogCopy ? (
        <ReasonDialog
          open
          title={dialogCopy.title}
          body={dialogCopy.body}
          confirmLabel={dialogCopy.confirm}
          danger={dialogCopy.danger}
          pending={actionM.isPending}
          onCancel={() => setPending(null)}
          onConfirm={(reason) => actionM.mutate({ p: pending, reason })}
        />
      ) : null}

      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="w-[min(94vw,460px)]">
          <form
            className="space-y-3"
            onSubmit={(e) => {
              e.preventDefault();
              if (editReason.trim().length >= 3) editM.mutate();
            }}
          >
            <DialogTitle>Edit user</DialogTitle>
            <label className="block space-y-1 text-sm">
              <span className="text-[var(--fg-muted)]">Display name</span>
              <Input value={name} onChange={(e) => setName(e.target.value)} maxLength={120} />
            </label>
            <label className="block space-y-1 text-sm">
              <span className="text-[var(--fg-muted)]">Role</span>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value)}
                className="h-10 w-full rounded-md border border-[var(--border)] bg-[var(--surface-2)] px-3 text-sm"
              >
                <option value="trader">Trader (normal customer)</option>
                <option value="viewer">Viewer (read only)</option>
              </select>
            </label>
            <label className="block space-y-1 text-sm">
              <span className="text-[var(--fg-muted)]">Reason (saved in the audit log)</span>
              <Input value={editReason} onChange={(e) => setEditReason(e.target.value)} maxLength={500} />
            </label>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={() => setEditOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={editReason.trim().length < 3 || editM.isPending}>
                {editM.isPending ? "Saving…" : "Save"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
