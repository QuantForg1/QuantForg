"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DeskError, DeskSkeleton, DeskTable } from "@/components/desk/primitives";
import { authApi, platformApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, str } from "@/lib/desk";

export default function ProfilePage() {
  const qc = useQueryClient();
  const profileQ = useQuery({
    queryKey: ["profile"],
    queryFn: platformApi.profile,
    retry: false,
  });
  const sessionsQ = useQuery({
    queryKey: ["sessions"],
    queryFn: platformApi.sessions,
    retry: false,
  });
  const devicesQ = useQuery({
    queryKey: ["devices"],
    queryFn: platformApi.devices,
    retry: false,
  });
  const activityQ = useQuery({
    queryKey: ["activity"],
    queryFn: platformApi.activity,
    retry: false,
  });

  const [form, setForm] = useState({
    full_name: "",
    username: "",
    bio: "",
    country_code: "",
    timezone: "",
    preferred_language: "",
    trading_experience: "",
    risk_level: "",
  });
  const [password, setPassword] = useState({ next: "" });

  useEffect(() => {
    if (!profileQ.data) return;
    const p = asRecord(profileQ.data);
    setForm({
      full_name: str(p.full_name, ""),
      username: str(p.username, ""),
      bio: str(p.bio, ""),
      country_code: str(p.country_code, ""),
      timezone: str(p.timezone, ""),
      preferred_language: str(p.preferred_language, ""),
      trading_experience: str(p.trading_experience, ""),
      risk_level: str(p.risk_level, ""),
    });
  }, [profileQ.data]);

  const save = useMutation({
    mutationFn: () => platformApi.updateProfile(form),
    onSuccess: async () => {
      toast.success("Profile updated");
      await qc.invalidateQueries({ queryKey: ["profile"] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Update failed"),
  });

  const changePw = useMutation({
    mutationFn: () => authApi.changePassword(password.next),
    onSuccess: () => {
      toast.success("Password changed");
      setPassword({ next: "" });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Password change failed"),
  });

  const revoke = useMutation({
    mutationFn: platformApi.revokeSession,
    onSuccess: async () => {
      toast.success("Session revoked");
      await qc.invalidateQueries({ queryKey: ["sessions"] });
    },
  });

  const p = asRecord(profileQ.data);
  const sessions = asList(sessionsQ.data).map(asRecord);
  const devices = asList(devicesQ.data).map(asRecord);
  const activity = asList(activityQ.data).map(asRecord);

  return (
    <div>
      <PageHeader
        title="Profile"
        description="Identity, trading preferences, and security controls."
        actions={
          <Button size="sm" disabled={save.isPending} onClick={() => save.mutate()}>
            Save profile
          </Button>
        }
      />

      {profileQ.isLoading ? (
        <DeskSkeleton rows={5} />
      ) : profileQ.isError ? (
        <DeskError message="Unable to load profile." onRetry={() => profileQ.refetch()} />
      ) : (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
          <Card>
            <CardHeader className="flex-row items-center gap-4">
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-[var(--accent-soft)] text-xl font-semibold text-[var(--accent)]">
                {str(form.full_name || form.username || "QF")
                  .slice(0, 2)
                  .toUpperCase()}
              </div>
              <div>
                <CardTitle>{form.full_name || "Trader"}</CardTitle>
                <p className="text-sm text-[var(--fg-muted)]">@{form.username || "username"}</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  <Badge tone="accent">{form.risk_level || "risk"}</Badge>
                  <Badge tone="neutral">{form.trading_experience || "experience"}</Badge>
                </div>
              </div>
            </CardHeader>
          </Card>

          <div className="grid gap-4 xl:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Personal Information</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-3 sm:grid-cols-2">
                {(
                  [
                    ["full_name", "Full name"],
                    ["username", "Username"],
                    ["country_code", "Country"],
                    ["timezone", "Timezone"],
                    ["preferred_language", "Language"],
                    ["trading_experience", "Trading experience"],
                    ["risk_level", "Risk level"],
                  ] as const
                ).map(([key, label]) => (
                  <div key={key} className="space-y-1.5">
                    <Label>{label}</Label>
                    <Input
                      value={form[key]}
                      onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
                    />
                  </div>
                ))}
                <div className="space-y-1.5 sm:col-span-2">
                  <Label>Bio</Label>
                  <Input
                    value={form.bio}
                    onChange={(e) => setForm((f) => ({ ...f, bio: e.target.value }))}
                  />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Security</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-1.5">
                  <Label>New password</Label>
                  <Input
                    type="password"
                    value={password.next}
                    onChange={(e) => setPassword({ next: e.target.value })}
                  />
                </div>
                <Button
                  variant="secondary"
                  disabled={changePw.isPending || password.next.length < 8}
                  onClick={() => changePw.mutate()}
                >
                  Update password
                </Button>
                <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-3 text-sm text-[var(--fg-muted)]">
                  <p className="font-medium text-[var(--fg)]">2FA</p>
                  <p className="mt-1 text-xs">
                    Two-factor authentication is managed through your Supabase auth provider settings.
                  </p>
                </div>
                <p className="text-xs text-[var(--fg-subtle)]">User {str(p.user_id)}</p>
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Sessions</CardTitle>
              </CardHeader>
              <CardContent>
                {sessions.length === 0 ? (
                  <p className="text-sm text-[var(--fg-muted)]">No sessions listed.</p>
                ) : (
                  <DeskTable
                    columns={["IP", "Active", "Last active", ""]}
                    rows={sessions.map((s) => [
                      str(s.ip_address),
                      <Badge key="a" tone={s.is_active ? "success" : "neutral"}>
                        {s.is_active ? "Active" : "Ended"}
                      </Badge>,
                      str(s.last_active_at).slice(0, 19),
                      <Button
                        key="r"
                        size="sm"
                        variant="ghost"
                        onClick={() => revoke.mutate(str(s.id))}
                      >
                        Revoke
                      </Button>,
                    ])}
                  />
                )}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Devices</CardTitle>
              </CardHeader>
              <CardContent>
                {devices.length === 0 ? (
                  <p className="text-sm text-[var(--fg-muted)]">No devices registered.</p>
                ) : (
                  <DeskTable
                    columns={["Label", "Last seen"]}
                    rows={devices.map((d) => [
                      str(d.device_label || d.user_agent).slice(0, 48),
                      str(d.last_seen_at).slice(0, 19),
                    ])}
                  />
                )}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Activity</CardTitle>
              </CardHeader>
              <CardContent>
                {activityQ.isLoading ? (
                  <DeskSkeleton rows={3} />
                ) : activity.length === 0 ? (
                  <p className="text-sm text-[var(--fg-muted)]">No recent activity.</p>
                ) : (
                  <DeskTable
                    columns={["When", "Action", "Message"]}
                    rows={activity.slice(0, 8).map((a) => [
                      str(a.created_at).slice(0, 16),
                      str(a.action),
                      str(a.message).slice(0, 64),
                    ])}
                  />
                )}
              </CardContent>
            </Card>
          </div>
        </motion.div>
      )}
    </div>
  );
}
