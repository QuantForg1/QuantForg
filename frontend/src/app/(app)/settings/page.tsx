"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { DeskError, DeskSkeleton, DeskTable } from "@/components/desk/primitives";
import { PageMotion } from "@/components/desk/motion";
import { authApi, platformApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, str } from "@/lib/desk";
import { clearSession } from "@/lib/auth/session";

const TABS = [
  "Appearance",
  "Security",
  "Notifications",
  "Workspace",
  "Sessions",
  "Danger Zone",
] as const;

export default function SettingsPage() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<(typeof TABS)[number]>("Appearance");
  const settingsQ = useQuery({
    queryKey: ["settings"],
    queryFn: platformApi.settings,
    retry: false,
  });
  const prefsQ = useQuery({
    queryKey: ["notification-prefs"],
    queryFn: platformApi.notificationPreferences,
    retry: false,
  });
  const sessionsQ = useQuery({
    queryKey: ["sessions"],
    queryFn: platformApi.sessions,
    retry: false,
    enabled: tab === "Sessions" || tab === "Security",
  });

  const [form, setForm] = useState({
    theme: "dark",
    notifications_enabled: true,
    email_marketing: false,
    email_security: true,
    email_product: true,
    security_login_alerts: true,
    security_require_reauth: false,
    session_timeout_minutes: 60,
  });
  const [newPassword, setNewPassword] = useState("");

  useEffect(() => {
    if (!settingsQ.data) return;
    const s = asRecord(settingsQ.data);
    setForm({
      theme: str(s.theme, "dark"),
      notifications_enabled: Boolean(s.notifications_enabled),
      email_marketing: Boolean(s.email_marketing),
      email_security: Boolean(s.email_security),
      email_product: Boolean(s.email_product),
      security_login_alerts: Boolean(s.security_login_alerts),
      security_require_reauth: Boolean(s.security_require_reauth),
      session_timeout_minutes: Number(s.session_timeout_minutes ?? 60),
    });
  }, [settingsQ.data]);

  const save = useMutation({
    mutationFn: () => platformApi.updateSettings(form),
    onSuccess: async () => {
      toast.success("Settings saved");
      await qc.invalidateQueries({ queryKey: ["settings"] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Save failed"),
  });

  const changePw = useMutation({
    mutationFn: () => authApi.changePassword(newPassword),
    onSuccess: () => {
      toast.success("Password updated");
      setNewPassword("");
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

  const prefs = asList(prefsQ.data).map(asRecord);
  const sessions = asList(sessionsQ.data).map(asRecord);

  return (
    <div>
      <PageHeader
        title="Settings"
        description="Appearance, security posture, notifications, sessions, and workspace controls."
        actions={
          tab !== "Danger Zone" ? (
            <Button size="sm" disabled={save.isPending} onClick={() => save.mutate()}>
              Save changes
            </Button>
          ) : null
        }
      />

      <div
        className="mb-5 flex flex-wrap gap-1.5"
        role="tablist"
        aria-label="Settings sections"
      >
        {TABS.map((t) => (
          <Button
            key={t}
            size="sm"
            role="tab"
            aria-selected={tab === t}
            variant={tab === t ? "default" : "ghost"}
            onClick={() => setTab(t)}
          >
            {t}
          </Button>
        ))}
      </div>

      {settingsQ.isLoading ? (
        <DeskSkeleton rows={4} />
      ) : settingsQ.isError ? (
        <DeskError message="Unable to load settings." onRetry={() => settingsQ.refetch()} />
      ) : (
        <PageMotion>
          {tab === "Appearance" ? (
            <Card className="qf-card-interactive">
              <CardHeader>
                <CardTitle>Appearance</CardTitle>
              </CardHeader>
              <CardContent className="grid max-w-xl gap-3">
                <div className="space-y-1.5">
                  <Label htmlFor="theme">Theme</Label>
                  <Input
                    id="theme"
                    value={form.theme}
                    onChange={(e) => setForm((f) => ({ ...f, theme: e.target.value }))}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="timeout">Session timeout (minutes)</Label>
                  <Input
                    id="timeout"
                    type="number"
                    value={form.session_timeout_minutes}
                    onChange={(e) =>
                      setForm((f) => ({
                        ...f,
                        session_timeout_minutes: Number(e.target.value),
                      }))
                    }
                  />
                </div>
              </CardContent>
            </Card>
          ) : null}

          {tab === "Security" ? (
            <div className="grid gap-4 lg:grid-cols-2">
              <Card className="qf-card-interactive">
                <CardHeader>
                  <CardTitle>Security controls</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <Toggle
                    label="Login alerts"
                    checked={form.security_login_alerts}
                    onChange={(v) => setForm((f) => ({ ...f, security_login_alerts: v }))}
                  />
                  <Toggle
                    label="Require re-authentication"
                    checked={form.security_require_reauth}
                    onChange={(v) => setForm((f) => ({ ...f, security_require_reauth: v }))}
                  />
                </CardContent>
              </Card>
              <Card className="qf-card-interactive">
                <CardHeader>
                  <CardTitle>Password</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="space-y-1.5">
                    <Label htmlFor="new-password">New password</Label>
                    <Input
                      id="new-password"
                      type="password"
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                    />
                  </div>
                  <Button
                    variant="secondary"
                    disabled={changePw.isPending || newPassword.length < 8}
                    onClick={() => changePw.mutate()}
                  >
                    Update password
                  </Button>
                </CardContent>
              </Card>
            </div>
          ) : null}

          {tab === "Notifications" ? (
            <Card className="qf-card-interactive">
              <CardHeader>
                <CardTitle>Notifications</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <Toggle
                  label="In-app notifications"
                  checked={form.notifications_enabled}
                  onChange={(v) => setForm((f) => ({ ...f, notifications_enabled: v }))}
                />
                <Toggle
                  label="Security emails"
                  checked={form.email_security}
                  onChange={(v) => setForm((f) => ({ ...f, email_security: v }))}
                />
                <Toggle
                  label="Product emails"
                  checked={form.email_product}
                  onChange={(v) => setForm((f) => ({ ...f, email_product: v }))}
                />
                <Toggle
                  label="Marketing emails"
                  checked={form.email_marketing}
                  onChange={(v) => setForm((f) => ({ ...f, email_marketing: v }))}
                />
                <div className="pt-2">
                  <p className="mb-2 text-xs uppercase tracking-wider text-[var(--fg-subtle)]">
                    Category preferences
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {prefs.length === 0 ? (
                      <p className="text-sm text-[var(--fg-muted)]">No category prefs returned.</p>
                    ) : (
                      prefs.map((p) => (
                        <Badge key={str(p.category)} tone="neutral">
                          {str(p.category)} · in-app {String(p.in_app)} · email {String(p.email)}
                        </Badge>
                      ))
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          ) : null}

          {tab === "Workspace" ? (
            <Card className="qf-card-interactive">
              <CardHeader>
                <CardTitle>Workspace</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm text-[var(--fg-muted)]">
                <p>
                  Manage members and invitations from Organizations. Desk preferences on this page
                  apply to your personal session.
                </p>
                <Button variant="secondary" asChild>
                  <a href="/organizations">Open organizations</a>
                </Button>
                <p className="text-xs text-[var(--fg-subtle)]">
                  Live execution remains gated by server-side <code>EXECUTION_ENABLED</code>.
                </p>
              </CardContent>
            </Card>
          ) : null}

          {tab === "Sessions" ? (
            <Card>
              <CardHeader>
                <CardTitle>Active sessions</CardTitle>
              </CardHeader>
              <CardContent>
                {sessionsQ.isLoading ? (
                  <DeskSkeleton rows={3} />
                ) : sessions.length === 0 ? (
                  <p className="text-sm text-[var(--fg-muted)]">No sessions listed.</p>
                ) : (
                  <DeskTable
                    columns={["IP", "Status", "Last active", ""]}
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
          ) : null}

          {tab === "Danger Zone" ? (
            <Card className="border-[var(--danger)]/40">
              <CardHeader>
                <CardTitle className="text-[var(--danger)]">Danger Zone</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-sm text-[var(--fg-muted)]">
                  Sign out of this browser session. Account deletion is managed by your organization
                  owner and is not available as a self-serve desk action.
                </p>
                <Button
                  variant="danger"
                  onClick={async () => {
                    try {
                      await authApi.logout();
                    } catch {
                      /* still clear local session */
                    }
                    clearSession();
                    window.location.href = "/login";
                  }}
                >
                  Sign out
                </Button>
              </CardContent>
            </Card>
          ) : null}
        </PageMotion>
      )}
    </div>
  );
}

function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className="flex w-full items-center justify-between rounded-lg border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2.5 text-left transition hover:border-[var(--border-strong)]"
    >
      <span className="text-sm text-[var(--fg)]">{label}</span>
      <Badge tone={checked ? "success" : "neutral"}>{checked ? "On" : "Off"}</Badge>
    </button>
  );
}
