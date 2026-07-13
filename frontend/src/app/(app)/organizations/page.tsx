"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Building2 } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DeskEmpty, DeskError, DeskSkeleton, DeskTable } from "@/components/desk/primitives";
import { platformApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, str } from "@/lib/desk";
import { useAuth } from "@/providers/auth-provider";

/** API role `member` is displayed as Trader (product language). */
type InviteRole = "admin" | "member" | "viewer";

const ROLE_LABEL: Record<string, string> = {
  owner: "Owner",
  admin: "Admin",
  member: "Trader",
  viewer: "Viewer",
};

const PERMISSION_MATRIX: Array<{ capability: string; owner: string; admin: string; trader: string; viewer: string }> =
  [
    { capability: "Create workspace", owner: "Yes", admin: "—", trader: "—", viewer: "—" },
    { capability: "Invite Admin", owner: "Yes", admin: "—", trader: "—", viewer: "—" },
    { capability: "Invite Trader / Viewer", owner: "Yes", admin: "Yes", trader: "—", viewer: "—" },
    { capability: "Assign Owner via invite", owner: "No", admin: "No", trader: "No", viewer: "No" },
    { capability: "Trading / execution UI", owner: "Yes", admin: "Yes", trader: "Yes", viewer: "View" },
    { capability: "Settings & billing ops", owner: "Yes", admin: "Limited", trader: "—", viewer: "—" },
  ];

function invitableRoles(isOwner: boolean): InviteRole[] {
  return isOwner ? ["admin", "member", "viewer"] : ["member", "viewer"];
}

export default function OrganizationsPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<InviteRole>("member");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const orgsQ = useQuery({
    queryKey: ["organizations"],
    queryFn: platformApi.organizations,
    retry: false,
  });

  const create = useMutation({
    mutationFn: () => platformApi.createOrganization({ name, slug }),
    onSuccess: async (data) => {
      const { recordAudit } = await import("@/lib/observability/audit");
      recordAudit("organization_change", "success", "Organization created", { slug });
      toast.success("Workspace created");
      setSelectedId(str(asRecord(data).id));
      setName("");
      setSlug("");
      await qc.invalidateQueries({ queryKey: ["organizations"] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Create failed"),
  });

  const invite = useMutation({
    mutationFn: () =>
      platformApi.inviteMember(selectedId!, { email: inviteEmail, role: inviteRole }),
    onSuccess: async () => {
      const { recordAudit } = await import("@/lib/observability/audit");
      recordAudit("organization_change", "success", "Member invited", {
        role: inviteRole,
      });
      toast.success("Invitation sent");
      setInviteEmail("");
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Invite failed"),
  });

  const orgs = asList(orgsQ.data).map(asRecord);
  const selected = orgs.find((o) => str(o.id) === selectedId) ?? orgs[0];
  const activeId = selected ? str(selected.id) : null;
  const isOwner = Boolean(
    selected && user?.id && str(selected.owner_user_id) === user.id,
  );
  const allowedRoles = useMemo(() => invitableRoles(isOwner), [isOwner]);

  return (
    <div>
      <PageHeader
        title="Organizations"
        description="Workspaces, membership, roles, and invitations."
      />

      {orgsQ.isLoading ? (
        <DeskSkeleton rows={4} />
      ) : orgsQ.isError ? (
        <DeskError message="Unable to load organizations." onRetry={() => orgsQ.refetch()} />
      ) : (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
          <div className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
            <Card>
              <CardHeader>
                <CardTitle>Workspaces</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {orgs.length === 0 ? (
                  <DeskEmpty
                    icon={Building2}
                    title="No organizations yet"
                    description="Create a workspace to collaborate with your desk."
                  />
                ) : (
                  orgs.map((o) => (
                    <button
                      key={str(o.id)}
                      type="button"
                      onClick={() => setSelectedId(str(o.id))}
                      className={`flex w-full items-center justify-between rounded-lg border px-3 py-2.5 text-left ${
                        activeId === str(o.id)
                          ? "border-[var(--accent)] bg-[var(--accent-soft)]"
                          : "border-[var(--border)]"
                      }`}
                    >
                      <div>
                        <p className="text-sm font-medium">{str(o.name)}</p>
                        <p className="text-xs text-[var(--fg-subtle)]">/{str(o.slug)}</p>
                      </div>
                      <Badge tone="neutral">{str(o.org_type)}</Badge>
                    </button>
                  ))
                )}
              </CardContent>
            </Card>

            <div className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Workspace card</CardTitle>
                </CardHeader>
                <CardContent>
                  {selected ? (
                    <div className="space-y-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-lg font-semibold">{str(selected.name)}</h3>
                        <Badge tone="accent">{str(selected.org_type)}</Badge>
                        <Badge tone={isOwner ? "success" : "neutral"}>
                          Your role · {isOwner ? ROLE_LABEL.owner : "Member"}
                        </Badge>
                      </div>
                      <p className="text-sm text-[var(--fg-muted)]">Slug · {str(selected.slug)}</p>
                      <p className="text-xs text-[var(--fg-subtle)]">
                        Owner · {str(selected.owner_user_id)}
                      </p>
                      <div className="grid gap-2 sm:grid-cols-4">
                        {(["owner", "admin", "member", "viewer"] as const).map((role) => (
                          <div
                            key={role}
                            className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)] px-3 py-3"
                          >
                            <p className="text-xs text-[var(--fg-subtle)]">{ROLE_LABEL[role]}</p>
                            <p className="mt-1 text-sm text-[var(--fg)]">
                              {role === "member" ? "API: member" : `API: ${role}`}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <p className="text-sm text-[var(--fg-muted)]">Select or create a workspace.</p>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Permissions</CardTitle>
                </CardHeader>
                <CardContent>
                  <DeskTable
                    columns={["Capability", "Owner", "Admin", "Trader", "Viewer"]}
                    rows={PERMISSION_MATRIX.map((r) => [
                      r.capability,
                      r.owner,
                      r.admin,
                      r.trader,
                      r.viewer,
                    ])}
                  />
                  <p className="mt-2 text-xs text-[var(--fg-muted)]">
                    Server enforces invite rules: Owner/Admin only; no Owner via invite; Admins
                    cannot invite Admins.
                  </p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Invitations</CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col gap-3 sm:flex-row sm:items-end">
                  <div className="flex-1 space-y-1.5">
                    <Label htmlFor="invite-email">Email</Label>
                    <Input
                      id="invite-email"
                      type="email"
                      value={inviteEmail}
                      onChange={(e) => setInviteEmail(e.target.value)}
                      placeholder="trader@desk.com"
                    />
                  </div>
                  <div className="space-y-1.5 sm:w-40">
                    <Label htmlFor="invite-role">Role</Label>
                    <select
                      id="invite-role"
                      className="flex h-10 w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 text-sm text-[var(--fg)]"
                      value={allowedRoles.includes(inviteRole) ? inviteRole : allowedRoles[0]}
                      onChange={(e) => setInviteRole(e.target.value as InviteRole)}
                      disabled={!isOwner && !selected}
                    >
                      {allowedRoles.map((role) => (
                        <option key={role} value={role}>
                          {ROLE_LABEL[role]}
                        </option>
                      ))}
                    </select>
                  </div>
                  <Button
                    disabled={!activeId || !inviteEmail || invite.isPending || (!isOwner && !selected)}
                    onClick={() => {
                      if (!isOwner && inviteRole === "admin") {
                        toast.error("Only owners can invite admins");
                        return;
                      }
                      setSelectedId(activeId);
                      invite.mutate();
                    }}
                  >
                    Send invite
                  </Button>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Create workspace</CardTitle>
                </CardHeader>
                <CardContent className="grid gap-3 sm:grid-cols-2">
                  <div className="space-y-1.5">
                    <Label>Name</Label>
                    <Input value={name} onChange={(e) => setName(e.target.value)} />
                  </div>
                  <div className="space-y-1.5">
                    <Label>Slug</Label>
                    <Input value={slug} onChange={(e) => setSlug(e.target.value)} />
                  </div>
                  <Button
                    className="sm:col-span-2"
                    disabled={!name || !slug || create.isPending}
                    onClick={() => create.mutate()}
                  >
                    Create organization
                  </Button>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Usage</CardTitle>
                </CardHeader>
                <CardContent className="text-sm text-[var(--fg-muted)]">
                  {orgs.length} workspace{orgs.length === 1 ? "" : "s"} in this account. Invite
                  members to collaborate on strategies, risk, and ops.
                </CardContent>
              </Card>
            </div>
          </div>
        </motion.div>
      )}
    </div>
  );
}
