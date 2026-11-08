"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
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
import { authApi, platformApi, supportDeskApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, str } from "@/lib/desk";
import { clearSession } from "@/lib/auth/session";
import { useAuth } from "@/providers/auth-provider";
import { SubscriptionPanel } from "@/components/settings/subscription-panel";
import { TRADING_SYMBOL } from "@/lib/trading/gold-only";
import { cn } from "@/lib/utils";

const TABS = [
  "Account",
  "Subscription",
  "Security",
  "Notifications",
  "Preferences",
  "Connections",
  "Danger Zone",
] as const;

const DESK_PREFS_KEY = "qf.desk.preferences.v1";

type DeskPreferencesV1 = {
  timeFormat: "12h" | "24h";
  dateFormat: "mdy" | "dmy" | "ymd";
  defaultSymbol: string;
  defaultTimeframe: string;
};

const DEFAULT_DESK_PREFS: DeskPreferencesV1 = {
  timeFormat: "24h",
  dateFormat: "ymd",
  defaultSymbol: TRADING_SYMBOL,
  defaultTimeframe: "H1",
};

function loadDeskPreferences(): DeskPreferencesV1 {
  if (typeof window === "undefined") return DEFAULT_DESK_PREFS;
  try {
    const raw = localStorage.getItem(DESK_PREFS_KEY);
    if (!raw) return DEFAULT_DESK_PREFS;
    const parsed = JSON.parse(raw) as Partial<DeskPreferencesV1>;
    return { ...DEFAULT_DESK_PREFS, ...parsed };
  } catch {
    return DEFAULT_DESK_PREFS;
  }
}

function saveDeskPreferences(prefs: DeskPreferencesV1) {
  localStorage.setItem(DESK_PREFS_KEY, JSON.stringify(prefs));
}

function isStrongPassword(pw: string): boolean {
  if (pw.length < 10) return false;
  if (!/[A-Z]/.test(pw)) return false;
  if (!/[a-z]/.test(pw)) return false;
  if (!/\d/.test(pw)) return false;
  if (!/[^A-Za-z0-9]/.test(pw)) return false;
  return true;
}

export default function SettingsPage() {
  const qc = useQueryClient();
  const { user } = useAuth();
  const [tab, setTab] = useState<(typeof TABS)[number]>("Account");

  const settingsQ = useQuery({
    queryKey: ["settings"],
    queryFn: platformApi.settings,
    retry: false,
  });
  const profileQ = useQuery({
    queryKey: ["profile"],
    queryFn: platformApi.profile,
    retry: false,
    enabled: tab === "Account" || tab === "Preferences",
  });
  const activityQ = useQuery({
    queryKey: ["activity"],
    queryFn: platformApi.activity,
    retry: false,
    enabled: tab === "Account",
  });
  const prefsQ = useQuery({
    queryKey: ["notification-prefs"],
    queryFn: platformApi.notificationPreferences,
    retry: false,
    enabled: tab === "Notifications",
  });
  const sessionsQ = useQuery({
    queryKey: ["sessions"],
    queryFn: platformApi.sessions,
    retry: false,
    enabled: tab === "Security" || tab === "Connections" || tab === "Danger Zone",
  });
  const devicesQ = useQuery({
    queryKey: ["devices"],
    queryFn: platformApi.devices,
    retry: false,
    enabled: tab === "Security" || tab === "Connections",
  });

  const [settingsForm, setSettingsForm] = useState({
    notifications_enabled: true,
    email_marketing: false,
    email_security: true,
    email_product: true,
    security_login_alerts: true,
    security_require_reauth: false,
    session_timeout_minutes: 60,
  });

  const [profileForm, setProfileForm] = useState({
    full_name: "",
    username: "",
    timezone: "",
  });

  const [deskPrefs, setDeskPrefs] = useState<DeskPreferencesV1>(DEFAULT_DESK_PREFS);
  const [newPassword, setNewPassword] = useState("");
  const [deletionNote, setDeletionNote] = useState("");

  useEffect(() => {
    setDeskPrefs(loadDeskPreferences());
  }, []);

  useEffect(() => {
    if (!settingsQ.data) return;
    const s = asRecord(settingsQ.data);
    setSettingsForm({
      notifications_enabled: Boolean(s.notifications_enabled),
      email_marketing: Boolean(s.email_marketing),
      email_security: Boolean(s.email_security),
      email_product: Boolean(s.email_product),
      security_login_alerts: Boolean(s.security_login_alerts),
      security_require_reauth: Boolean(s.security_require_reauth),
      session_timeout_minutes: Number(s.session_timeout_minutes ?? 60),
    });
  }, [settingsQ.data]);

  useEffect(() => {
    if (!profileQ.data) return;
    const p = asRecord(profileQ.data);
    setProfileForm({
      full_name: str(p.full_name, ""),
      username: str(p.username, ""),
      timezone: str(p.timezone, ""),
    });
  }, [profileQ.data]);

  const saveSettings = useMutation({
    mutationFn: () =>
      platformApi.updateSettings({
        ...settingsForm,
        theme: "dark",
      }),
    onSuccess: async () => {
      const { recordAudit } = await import("@/lib/observability/audit");
      recordAudit("settings_change", "success", "Settings updated");
      toast.success("Settings saved");
      await qc.invalidateQueries({ queryKey: ["settings"] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Save failed"),
  });

  const saveProfile = useMutation({
    mutationFn: () =>
      platformApi.updateProfile({
        full_name: profileForm.full_name,
        username: profileForm.username,
        timezone: profileForm.timezone,
      }),
    onSuccess: async () => {
      toast.success("Profile updated");
      await qc.invalidateQueries({ queryKey: ["profile"] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Profile update failed"),
  });

  const changePw = useMutation({
    mutationFn: () => authApi.changePassword(newPassword),
    onSuccess: async () => {
      const { recordAudit } = await import("@/lib/observability/audit");
      recordAudit("password_reset", "success", "Password changed");
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
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Revoke failed"),
  });

  const updatePref = useMutation({
    mutationFn: (input: { category: string; in_app?: boolean; email?: boolean }) =>
      platformApi.updateNotificationPreference(input.category, {
        in_app: input.in_app,
        email: input.email,
      }),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["notification-prefs"] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Preference update failed"),
  });

  const requestDeletion = useMutation({
    mutationFn: () =>
      supportDeskApi.createTicket({
        subject: "Account deletion request",
        body:
          deletionNote.trim() ||
          "Please process an account deletion request for my QuantForg user.",
        category: "account",
      }),
    onSuccess: () => {
      toast.success("Deletion request submitted to support");
      setDeletionNote("");
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Request failed"),
  });

  const prefs = asList(prefsQ.data).map(asRecord);
  const sessions = asList(sessionsQ.data).map(asRecord);
  const devices = asList(devicesQ.data).map(asRecord);
  const activity = asList(activityQ.data).map(asRecord);

  const passwordOk = useMemo(() => isStrongPassword(newPassword), [newPassword]);

  const headerSaveVisible =
    tab === "Security" || tab === "Notifications" || tab === "Preferences";

  const onHeaderSave = () => {
    if (tab === "Preferences") {
      saveDeskPreferences(deskPrefs);
      saveProfile.mutate();
      return;
    }
    if (tab === "Security" || tab === "Notifications") {
      saveSettings.mutate();
    }
  };

  async function revokeAllSessions() {
    if (sessions.length === 0) {
      toast.message("No sessions to revoke");
      return;
    }
    try {
      await Promise.all(sessions.map((s) => platformApi.revokeSession(str(s.id))));
      toast.success("All sessions revoked");
      await qc.invalidateQueries({ queryKey: ["sessions"] });
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not revoke all sessions");
    }
  }

  const pageLoading = settingsQ.isLoading;
  const pageError = settingsQ.isError;

  return (
    <div>
      <PageHeader
        title="Settings"
        description="Account, security, notifications, and workspace preferences."
        actions={
          tab === "Account" ? (
            <Button size="sm" disabled={saveProfile.isPending} onClick={() => saveProfile.mutate()}>
              Save profile
            </Button>
          ) : headerSaveVisible ? (
            <Button
              size="sm"
              disabled={
                tab === "Preferences"
                  ? saveProfile.isPending
                  : saveSettings.isPending
              }
              onClick={onHeaderSave}
            >
              Save changes
            </Button>
          ) : null
        }
      />

      <div
        className="mb-[var(--space-4)] flex flex-wrap gap-1 rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] p-1"
        role="tablist"
        aria-label="Settings sections"
      >
        {TABS.map((t) => (
          <Button
            key={t}
            size="sm"
            role="tab"
            aria-selected={tab === t}
            variant="ghost"
            className={
              tab === t
                ? "h-8 bg-[var(--accent-soft)] text-[var(--accent)]"
                : "h-8 text-[var(--fg-muted)]"
            }
            onClick={() => setTab(t)}
          >
            {t}
          </Button>
        ))}
      </div>

      {pageLoading ? (
        <DeskSkeleton rows={4} />
      ) : pageError ? (
        <DeskError message="Unable to load settings." onRetry={() => settingsQ.refetch()} />
      ) : (
        <PageMotion>
          {tab === "Account" ? (
            <div className="grid gap-4 xl:grid-cols-2">
              <Card className="qf-card-interactive">
                <CardHeader>
                  <CardTitle>Profile</CardTitle>
                </CardHeader>
                <CardContent className="grid gap-3">
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="space-y-1.5">
                      <Label htmlFor="full-name">Display name</Label>
                      <Input
                        id="full-name"
                        value={profileForm.full_name}
                        onChange={(e) =>
                          setProfileForm((f) => ({ ...f, full_name: e.target.value }))
                        }
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor="username">Username</Label>
                      <Input
                        id="username"
                        value={profileForm.username}
                        onChange={(e) =>
                          setProfileForm((f) => ({ ...f, username: e.target.value }))
                        }
                      />
                    </div>
                  </div>
                  <div className="space-y-1">
                    <p className="text-[11px] uppercase tracking-wide text-[var(--fg-subtle)]">
                      Email
                    </p>
                    <p className="text-sm text-[var(--fg)]">{user?.email || "Unavailable"}</p>
                  </div>
                  <div className="space-y-1">
                    <p className="text-[11px] uppercase tracking-wide text-[var(--fg-subtle)]">
                      User ID
                    </p>
                    <p className="font-mono text-xs text-[var(--fg-muted)]">
                      {user?.id || "Unavailable"}
                    </p>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Recent activity</CardTitle>
                </CardHeader>
                <CardContent>
                  {activityQ.isLoading ? (
                    <DeskSkeleton rows={4} />
                  ) : activity.length === 0 ? (
                    <p className="text-sm text-[var(--fg-muted)]">No recent activity recorded.</p>
                  ) : (
                    <DeskTable
                      columns={["Event", "When"]}
                      rows={activity.slice(0, 12).map((row) => [
                        str(row.action || row.event || row.kind, "Activity"),
                        str(row.created_at || row.timestamp, "—").slice(0, 19),
                      ])}
                    />
                  )}
                </CardContent>
              </Card>
            </div>
          ) : null}

          {tab === "Subscription" ? <SubscriptionPanel /> : null}

          {tab === "Security" ? (
            <div className="grid gap-4 lg:grid-cols-2">
              <Card className="qf-card-interactive">
                <CardHeader>
                  <CardTitle>Security controls</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <Toggle
                    label="Login alerts"
                    checked={settingsForm.security_login_alerts}
                    onChange={(v) =>
                      setSettingsForm((f) => ({ ...f, security_login_alerts: v }))
                    }
                  />
                  <Toggle
                    label="Require re-authentication"
                    checked={settingsForm.security_require_reauth}
                    onChange={(v) =>
                      setSettingsForm((f) => ({ ...f, security_require_reauth: v }))
                    }
                  />
                  <div className="space-y-1.5 pt-1">
                    <Label htmlFor="session-timeout">Session timeout (minutes)</Label>
                    <Input
                      id="session-timeout"
                      type="number"
                      min={5}
                      value={settingsForm.session_timeout_minutes}
                      onChange={(e) =>
                        setSettingsForm((f) => ({
                          ...f,
                          session_timeout_minutes: Number(e.target.value),
                        }))
                      }
                    />
                  </div>
                  <p className="text-xs text-[var(--fg-subtle)]">
                    Two-factor authentication is not enabled on this account yet. Contact support if
                    you need elevated protection.
                  </p>
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
                      autoComplete="new-password"
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                    />
                  </div>
                  <p className="text-xs text-[var(--fg-subtle)]">
                    At least 10 characters with uppercase, lowercase, digit, and symbol.
                  </p>
                  <Button
                    variant="secondary"
                    disabled={changePw.isPending || !passwordOk}
                    onClick={() => changePw.mutate()}
                  >
                    Update password
                  </Button>
                </CardContent>
              </Card>

              <Card className="lg:col-span-2">
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
                          disabled={revoke.isPending}
                          onClick={() => revoke.mutate(str(s.id))}
                        >
                          Revoke
                        </Button>,
                      ])}
                    />
                  )}
                </CardContent>
              </Card>

              <Card className="lg:col-span-2">
                <CardHeader>
                  <CardTitle>Trusted devices</CardTitle>
                </CardHeader>
                <CardContent>
                  {devicesQ.isLoading ? (
                    <DeskSkeleton rows={3} />
                  ) : devices.length === 0 ? (
                    <p className="text-sm text-[var(--fg-muted)]">No devices on file.</p>
                  ) : (
                    <DeskTable
                      columns={["Device", "Last seen", "Status"]}
                      rows={devices.map((d) => [
                        str(d.label || d.device_name || d.user_agent, "Device"),
                        str(d.last_seen_at || d.last_active_at, "—").slice(0, 19),
                        <Badge key="s" tone={d.trusted === false ? "warning" : "neutral"}>
                          {d.trusted === false ? "Unverified" : "Known"}
                        </Badge>,
                      ])}
                    />
                  )}
                </CardContent>
              </Card>
            </div>
          ) : null}

          {tab === "Notifications" ? (
            <Card className="qf-card-interactive">
              <CardHeader>
                <CardTitle>Notifications</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <Toggle
                  label="In-app notifications"
                  checked={settingsForm.notifications_enabled}
                  onChange={(v) => setSettingsForm((f) => ({ ...f, notifications_enabled: v }))}
                />
                <Toggle
                  label="Security emails"
                  checked={settingsForm.email_security}
                  onChange={(v) => setSettingsForm((f) => ({ ...f, email_security: v }))}
                />
                <Toggle
                  label="Product emails"
                  checked={settingsForm.email_product}
                  onChange={(v) => setSettingsForm((f) => ({ ...f, email_product: v }))}
                />
                <Toggle
                  label="Marketing emails"
                  checked={settingsForm.email_marketing}
                  onChange={(v) => setSettingsForm((f) => ({ ...f, email_marketing: v }))}
                />

                <div className="border-t border-[var(--border)] pt-4">
                  <p className="mb-3 text-xs uppercase tracking-wider text-[var(--fg-subtle)]">
                    Category preferences
                  </p>
                  {prefsQ.isLoading ? (
                    <DeskSkeleton rows={2} />
                  ) : prefs.length === 0 ? (
                    <p className="text-sm text-[var(--fg-muted)]">No category preferences yet.</p>
                  ) : (
                    <ul className="space-y-2">
                      {prefs.map((p) => {
                        const category = str(p.category);
                        const inApp = Boolean(p.in_app);
                        const email = Boolean(p.email);
                        return (
                          <li
                            key={category}
                            className="flex flex-wrap items-center justify-between gap-2 rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2"
                          >
                            <span className="text-sm font-medium text-[var(--fg)]">{category}</span>
                            <div className="flex flex-wrap gap-2">
                              <CategoryToggle
                                label="In-app"
                                checked={inApp}
                                disabled={updatePref.isPending}
                                onChange={(v) =>
                                  updatePref.mutate({ category, in_app: v, email })
                                }
                              />
                              <CategoryToggle
                                label="Email"
                                checked={email}
                                disabled={updatePref.isPending}
                                onChange={(v) =>
                                  updatePref.mutate({ category, email: v, in_app: inApp })
                                }
                              />
                            </div>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </div>
              </CardContent>
            </Card>
          ) : null}

          {tab === "Preferences" ? (
            <div className="grid gap-4 lg:grid-cols-2">
              <Card className="qf-card-interactive">
                <CardHeader>
                  <CardTitle>Timezone</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="space-y-1.5">
                    <Label htmlFor="timezone">IANA timezone</Label>
                    <Input
                      id="timezone"
                      placeholder="e.g. America/New_York"
                      value={profileForm.timezone}
                      onChange={(e) =>
                        setProfileForm((f) => ({ ...f, timezone: e.target.value }))
                      }
                    />
                  </div>
                  <p className="text-xs text-[var(--fg-subtle)]">
                    Stored on your platform profile and used for scheduled notifications.
                  </p>
                </CardContent>
              </Card>

              <Card className="qf-card-interactive">
                <CardHeader>
                  <CardTitle>Desk defaults</CardTitle>
                </CardHeader>
                <CardContent className="grid gap-3 sm:grid-cols-2">
                  <SelectField
                    id="time-format"
                    label="Time format"
                    value={deskPrefs.timeFormat}
                    options={[
                      { value: "12h", label: "12-hour" },
                      { value: "24h", label: "24-hour" },
                    ]}
                    onChange={(v) =>
                      setDeskPrefs((p) => ({ ...p, timeFormat: v as DeskPreferencesV1["timeFormat"] }))
                    }
                  />
                  <SelectField
                    id="date-format"
                    label="Date format"
                    value={deskPrefs.dateFormat}
                    options={[
                      { value: "mdy", label: "MM/DD/YYYY" },
                      { value: "dmy", label: "DD/MM/YYYY" },
                      { value: "ymd", label: "YYYY-MM-DD" },
                    ]}
                    onChange={(v) =>
                      setDeskPrefs((p) => ({
                        ...p,
                        dateFormat: v as DeskPreferencesV1["dateFormat"],
                      }))
                    }
                  />
                  <div className="space-y-1.5">
                    <Label htmlFor="default-symbol">Default symbol</Label>
                    <Input
                      id="default-symbol"
                      value={deskPrefs.defaultSymbol}
                      onChange={(e) =>
                        setDeskPrefs((p) => ({ ...p, defaultSymbol: e.target.value }))
                      }
                    />
                  </div>
                  <SelectField
                    id="default-timeframe"
                    label="Default timeframe"
                    value={deskPrefs.defaultTimeframe}
                    options={[
                      { value: "M15", label: "M15" },
                      { value: "H1", label: "H1" },
                      { value: "H4", label: "H4" },
                      { value: "D1", label: "D1" },
                    ]}
                    onChange={(v) => setDeskPrefs((p) => ({ ...p, defaultTimeframe: v }))}
                  />
                  <p className="sm:col-span-2 text-xs text-[var(--fg-subtle)]">
                    Saved in this browser only ({DESK_PREFS_KEY}). Clearing site data removes these
                    defaults.
                  </p>
                </CardContent>
              </Card>
            </div>
          ) : null}

          {tab === "Connections" ? (
            <div className="grid gap-4 lg:grid-cols-2">
              <Card className="qf-card-interactive">
                <CardHeader>
                  <CardTitle>Broker</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <p className="text-sm text-[var(--fg-muted)]">
                    MT5 credentials and live trading authorization are managed on the Broker desk.
                  </p>
                  <Button variant="secondary" asChild>
                    <Link href="/broker">Open Broker desk</Link>
                  </Button>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Session summary</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 text-sm text-[var(--fg-muted)]">
                  <p>
                    <span className="text-[var(--fg)]">{sessions.length}</span> active platform
                    session{sessions.length === 1 ? "" : "s"}
                  </p>
                  <p>
                    <span className="text-[var(--fg)]">{devices.length}</span> known device
                    {devices.length === 1 ? "" : "s"}
                  </p>
                </CardContent>
              </Card>
            </div>
          ) : null}

          {tab === "Danger Zone" ? (
            <Card className="border-[var(--danger)]/40">
              <CardHeader>
                <CardTitle className="text-[var(--danger)]">Danger Zone</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-sm text-[var(--fg-muted)]">
                  Irreversible or high-impact account actions. Use with care.
                </p>
                <div className="flex flex-wrap gap-2">
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
                  <Button
                    variant="secondary"
                    disabled={sessionsQ.isLoading || sessions.length === 0}
                    onClick={() => void revokeAllSessions()}
                  >
                    Revoke all sessions
                  </Button>
                </div>
                <div className="space-y-2 border-t border-[var(--border)] pt-4">
                  <p className="text-sm font-medium text-[var(--fg)]">Request account deletion</p>
                  <Label htmlFor="deletion-note">Reason (optional)</Label>
                  <Input
                    id="deletion-note"
                    value={deletionNote}
                    onChange={(e) => setDeletionNote(e.target.value)}
                    placeholder="Tell support why you are leaving"
                  />
                  <Button
                    variant="danger"
                    disabled={requestDeletion.isPending}
                    onClick={() => requestDeletion.mutate()}
                  >
                    Submit deletion request
                  </Button>
                </div>
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
      className="flex w-full items-center justify-between rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2.5 text-left transition hover:border-[var(--border-strong)]"
    >
      <span className="text-sm text-[var(--fg)]">{label}</span>
      <Badge tone={checked ? "success" : "neutral"}>{checked ? "On" : "Off"}</Badge>
    </button>
  );
}

function CategoryToggle({
  label,
  checked,
  disabled,
  onChange,
}: {
  label: string;
  checked: boolean;
  disabled?: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        "rounded-md border border-[var(--border)] px-2 py-1 text-xs",
        checked ? "bg-[var(--accent-soft)] text-[var(--accent)]" : "text-[var(--fg-muted)]",
        disabled && "opacity-60",
      )}
    >
      {label}: {checked ? "On" : "Off"}
    </button>
  );
}

function SelectField({
  id,
  label,
  value,
  options,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  options: Array<{ value: string; label: string }>;
  onChange: (value: string) => void;
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="flex h-10 w-full rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--bg-elevated)] px-3 text-sm text-[var(--fg)]"
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}
