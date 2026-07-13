"use client";

import { useState } from "react";
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
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { platformApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, str } from "@/lib/desk";

export default function OrganizationsPage() {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const orgsQ = useQuery({
    queryKey: ["organizations"],
    queryFn: platformApi.organizations,
    retry: false,
  });

  const create = useMutation({
    mutationFn: () => platformApi.createOrganization({ name, slug }),
    onSuccess: async (data) => {
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
      platformApi.inviteMember(selectedId!, { email: inviteEmail, role: "member" }),
    onSuccess: () => {
      toast.success("Invitation sent");
      setInviteEmail("");
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Invite failed"),
  });

  const orgs = asList(orgsQ.data).map(asRecord);
  const selected = orgs.find((o) => str(o.id) === selectedId) ?? orgs[0];
  const activeId = selected ? str(selected.id) : null;

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
                      </div>
                      <p className="text-sm text-[var(--fg-muted)]">Slug · {str(selected.slug)}</p>
                      <p className="text-xs text-[var(--fg-subtle)]">
                        Owner · {str(selected.owner_user_id)}
                      </p>
                      <div className="grid gap-2 sm:grid-cols-3">
                        {["Members", "Roles", "Permissions"].map((label) => (
                          <div
                            key={label}
                            className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)] px-3 py-3"
                          >
                            <p className="text-xs text-[var(--fg-subtle)]">{label}</p>
                            <p className="mt-1 text-sm text-[var(--fg)]">Managed via invites</p>
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
                  <CardTitle>Invitations</CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col gap-3 sm:flex-row sm:items-end">
                  <div className="flex-1 space-y-1.5">
                    <Label>Email</Label>
                    <Input
                      type="email"
                      value={inviteEmail}
                      onChange={(e) => setInviteEmail(e.target.value)}
                      placeholder="trader@desk.com"
                    />
                  </div>
                  <Button
                    disabled={!activeId || !inviteEmail || invite.isPending}
                    onClick={() => {
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
