"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AtSign,
  Bell,
  Clock,
  Coins,
  Copy,
  CreditCard,
  Hash,
  Link2,
  Mail,
  Monitor,
  Pencil,
  Settings as SettingsIcon,
  Shield,
  SlidersHorizontal,
  UserRound,
  Zap,
} from "lucide-react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { DeskError, DeskSkeleton, DeskTable } from "@/components/desk/primitives";
import { PageMotion } from "@/components/desk/motion";
import { authApi, platformApi, supportDeskApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, str } from "@/lib/desk";
import { clearSession } from "@/lib/auth/session";
import { useAuth } from "@/providers/auth-provider";
import { SubscriptionPanel } from "@/components/settings/subscription-panel";
import { MfaSecurityPanel } from "@/components/settings/mfa-security-panel";
import { TRADING_SYMBOL } from "@/lib/trading/gold-only";
import { cn } from "@/lib/utils";

const TABS = [
  "Account",
  "Subscription",
  "Security",
  "Notifications",
  "Preferences",
  "Connections",
] as const;

const TAB_ICON = {
  Account: UserRound,
  Subscription: CreditCard,
  Security: Shield,
  Notifications: Bell,
  Preferences: SlidersHorizontal,
  Connections: Link2,
} as const;

const DISPLAY_PREFS_KEY = "qf.settings.display.v1";

type DisplayPrefs = {
  lot: string;
  orderType: "market" | "limit";
  slippage: string;
  confirmBeforeOrder: boolean;
  advancedMode: boolean;
  numberFormat: "comma" | "dot";
};

const DEFAULT_DISPLAY_PREFS: DisplayPrefs = {
  lot: "0.01",
  orderType: "market",
  slippage: "0.50",
  confirmBeforeOrder: true,
  advancedMode: false,
  numberFormat: "comma",
};

const TIME_ZONES = [
  "Africa/Kigali",
  "Africa/Johannesburg",
  "Europe/London",
  "America/New_York",
  "UTC",
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
  defaultTimeframe: "M15",
};

function deskPrefsFromSettings(record: Record<string, unknown>): DeskPreferencesV1 {
  const timeFormat = str(record.time_format, DEFAULT_DESK_PREFS.timeFormat);
  const dateFormat = str(record.date_format, DEFAULT_DESK_PREFS.dateFormat);
  return {
    timeFormat:
      timeFormat === "12h" || timeFormat === "24h" ? timeFormat : DEFAULT_DESK_PREFS.timeFormat,
    dateFormat:
      dateFormat === "mdy" || dateFormat === "dmy" || dateFormat === "ymd"
        ? dateFormat
        : DEFAULT_DESK_PREFS.dateFormat,
    defaultSymbol: str(record.default_symbol, DEFAULT_DESK_PREFS.defaultSymbol),
    defaultTimeframe: str(record.default_timeframe, DEFAULT_DESK_PREFS.defaultTimeframe),
  };
}

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

type PendingConfirm = {
  title: string;
  body: string;
  confirmLabel: string;
  danger?: boolean;
  action: () => void;
};

function formatWhen(raw: string): string {
  if (!raw || raw === "—") return "—";
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) return raw.slice(0, 19).replace("T", " ");
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(parsed);
}

function numericUserId(id: string | undefined): string {
  if (!id) return "";
  if (/^\d+$/.test(id)) return id;
  const hex = id.replace(/[^0-9a-f]/gi, "");
  if (hex.length >= 8) {
    const n = Number.parseInt(hex.slice(-8), 16);
    if (Number.isFinite(n) && n > 0) return String(n);
  }
  return id.replace(/\D/g, "");
}

function loadDisplayPrefs(): DisplayPrefs {
  if (typeof window === "undefined") return DEFAULT_DISPLAY_PREFS;
  try {
    const raw = localStorage.getItem(DISPLAY_PREFS_KEY);
    if (!raw) return DEFAULT_DISPLAY_PREFS;
    return { ...DEFAULT_DISPLAY_PREFS, ...(JSON.parse(raw) as Partial<DisplayPrefs>) };
  } catch {
    return DEFAULT_DISPLAY_PREFS;
  }
}

function labelize(value: string): string {
  const cleaned = value.replaceAll("_", " ").trim();
  if (!cleaned) return "Preference";
  return cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
}

async function copyText(value: string, label: string) {
  try {
    await navigator.clipboard.writeText(value);
    toast.success(`${label} copied`);
  } catch {
    toast.error("Copy is unavailable in this browser");
  }
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
    enabled: tab === "Security" || tab === "Connections",
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
  const [displayPrefs, setDisplayPrefs] = useState<DisplayPrefs>(DEFAULT_DISPLAY_PREFS);
  const deskPrefsHydratedRef = useRef(false);
  const [newPassword, setNewPassword] = useState("");
  const [deletionNote, setDeletionNote] = useState("");
  const [confirm, setConfirm] = useState<PendingConfirm | null>(null);

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
    setDisplayPrefs(loadDisplayPrefs());
  }, []);

  useEffect(() => {
    if (!settingsQ.data || deskPrefsHydratedRef.current) return;

    const fromServer = deskPrefsFromSettings(asRecord(settingsQ.data));
    const local = loadDeskPreferences();
    const hasLocal =
      typeof window !== "undefined" && Boolean(localStorage.getItem(DESK_PREFS_KEY));

    if (hasLocal) {
      deskPrefsHydratedRef.current = true;
      void (async () => {
        try {
          await platformApi.updateSettings({
            theme: "dark",
            default_symbol: local.defaultSymbol,
            default_timeframe: local.defaultTimeframe,
            date_format: local.dateFormat,
            time_format: local.timeFormat,
          });
          setDeskPrefs(local);
          saveDeskPreferences(local);
          await qc.invalidateQueries({ queryKey: ["settings"] });
        } catch (e) {
          deskPrefsHydratedRef.current = false;
          setDeskPrefs(fromServer);
          toast.error(e instanceof ApiError ? e.message : "Could not migrate desk preferences");
        }
      })();
      return;
    }

    deskPrefsHydratedRef.current = true;
    setDeskPrefs(fromServer);
  }, [settingsQ.data, qc]);

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

  const saveDeskPrefs = useMutation({
    mutationFn: () =>
      platformApi.updateSettings({
        theme: "dark",
        default_symbol: deskPrefs.defaultSymbol,
        default_timeframe: deskPrefs.defaultTimeframe,
        date_format: deskPrefs.dateFormat,
        time_format: deskPrefs.timeFormat,
      }),
    onSuccess: async () => {
      saveDeskPreferences(deskPrefs);
      const { recordAudit } = await import("@/lib/observability/audit");
      recordAudit("settings_change", "success", "Desk preferences updated");
      toast.success("Desk preferences saved");
      await qc.invalidateQueries({ queryKey: ["settings"] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Desk preferences save failed"),
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
  const passwordOk = useMemo(() => isStrongPassword(newPassword), [newPassword]);

  const profileDirty = useMemo(() => {
    if (!profileQ.data) return false;
    const p = asRecord(profileQ.data);
    return (
      str(p.full_name, "") !== profileForm.full_name ||
      str(p.username, "") !== profileForm.username ||
      str(p.timezone, "") !== profileForm.timezone
    );
  }, [profileQ.data, profileForm]);

  const settingsDirty = useMemo(() => {
    if (!settingsQ.data) return false;
    const s = asRecord(settingsQ.data);
    return (
      Boolean(s.notifications_enabled) !== settingsForm.notifications_enabled ||
      Boolean(s.email_marketing) !== settingsForm.email_marketing ||
      Boolean(s.email_security) !== settingsForm.email_security ||
      Boolean(s.email_product) !== settingsForm.email_product ||
      Boolean(s.security_login_alerts) !== settingsForm.security_login_alerts ||
      Boolean(s.security_require_reauth) !== settingsForm.security_require_reauth ||
      Number(s.session_timeout_minutes ?? 60) !== settingsForm.session_timeout_minutes
    );
  }, [settingsQ.data, settingsForm]);

  const deskDirty = useMemo(() => {
    if (!settingsQ.data) return false;
    const saved = deskPrefsFromSettings(asRecord(settingsQ.data));
    return (
      saved.timeFormat !== deskPrefs.timeFormat ||
      saved.dateFormat !== deskPrefs.dateFormat ||
      saved.defaultSymbol !== deskPrefs.defaultSymbol ||
      saved.defaultTimeframe !== deskPrefs.defaultTimeframe
    );
  }, [settingsQ.data, deskPrefs]);

  const headerSaveVisible =
    tab === "Security" || tab === "Notifications" || tab === "Preferences";

  const onHeaderSave = () => {
    if (tab === "Preferences") {
      saveDeskPrefs.mutate();
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
  const unsaved =
    tab === "Account"
      ? profileDirty || deskDirty || settingsDirty
      : tab === "Preferences"
        ? profileDirty || deskDirty
        : headerSaveVisible
          ? settingsDirty
          : false;
  const savePending =
    tab === "Account" || tab === "Preferences"
      ? saveProfile.isPending || saveDeskPrefs.isPending || saveSettings.isPending
      : saveSettings.isPending;

  function updateDisplay(next: Partial<DisplayPrefs>) {
    setDisplayPrefs((current) => {
      const saved = { ...current, ...next };
      localStorage.setItem(DISPLAY_PREFS_KEY, JSON.stringify(saved));
      return saved;
    });
  }

  function selectTab(next: (typeof TABS)[number]) {
    setTab(next);
  }

  const shownUserId = numericUserId(user?.id);
  const profileTitle = profileForm.full_name || user?.display_name || "Account";
  const initials =
    profileTitle
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase() ?? "")
      .join("") || "QF";
  const verified = ["active", "verified", "enabled"].includes(
    String(user?.status || "").toLowerCase(),
  );
  const zoneOptions =
    profileForm.timezone &&
    !(TIME_ZONES as readonly string[]).includes(profileForm.timezone)
      ? [profileForm.timezone, ...TIME_ZONES]
      : [...TIME_ZONES];
  const today = new Date();
  const dateChoices = [
    {
      value: "mdy",
      label: new Intl.DateTimeFormat("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      }).format(today),
    },
    {
      value: "dmy",
      label: new Intl.DateTimeFormat("en-GB", {
        day: "numeric",
        month: "short",
        year: "numeric",
      }).format(today),
    },
    { value: "ymd", label: today.toISOString().slice(0, 10) },
  ];

  return (
    <div className="qf-desk mx-auto w-full min-w-0 max-w-6xl">
      <header className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex min-w-0 items-start gap-3">
          <span className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[var(--accent-soft)] text-[var(--accent)] shadow-[var(--shadow-card)]">
            <SettingsIcon className="h-5 w-5" aria-hidden />
          </span>
          <div className="min-w-0">
            <h1 className="text-xl font-semibold tracking-tight text-[var(--fg)] sm:text-2xl">
              Settings
            </h1>
            <p className="mt-1 max-w-xl text-sm text-[var(--fg-muted)]">
              Manage your account, trading, and platform preferences.
            </p>
          </div>
        </div>
        {tab === "Account" || headerSaveVisible ? (
          <div className="flex items-center gap-3">
            {unsaved ? (
              <span className="text-xs text-[var(--fg-subtle)]">Unsaved changes</span>
            ) : null}
            <Button
              size="sm"
              disabled={savePending || !unsaved}
              onClick={() => {
                if (tab === "Account" || tab === "Preferences") {
                  if (profileDirty) saveProfile.mutate();
                  if (deskDirty) saveDeskPrefs.mutate();
                  if (tab === "Account" && settingsDirty) saveSettings.mutate();
                  return;
                }
                onHeaderSave();
              }}
            >
              {savePending ? "Saving…" : tab === "Account" ? "Save profile" : "Save changes"}
            </Button>
          </div>
        ) : null}
      </header>

      <div className="mb-5 min-w-0 overflow-x-auto scrollbar-none">
        <div
          className="flex min-w-max gap-2"
          role="tablist"
          aria-label="Settings sections"
          onKeyDown={(e) => {
            if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
            e.preventDefault();
            const index = TABS.indexOf(tab);
            const next =
              e.key === "ArrowRight"
                ? TABS[(index + 1) % TABS.length]
                : TABS[(index - 1 + TABS.length) % TABS.length];
            selectTab(next);
            document.getElementById(`settings-tab-${next}`)?.focus();
          }}
        >
          {TABS.map((t) => {
            const Icon = TAB_ICON[t];
            return (
              <button
                key={t}
                id={`settings-tab-${t}`}
                type="button"
                role="tab"
                aria-selected={tab === t}
                aria-controls="settings-panel"
                tabIndex={tab === t ? 0 : -1}
                className={cn(
                  "inline-flex h-11 shrink-0 items-center gap-2 rounded-full px-4 text-sm font-medium transition-[background-color,color,box-shadow] duration-[var(--duration-fast)]",
                  tab === t
                    ? "bg-[var(--accent)] text-[var(--accent-fg)] shadow-[0_10px_24px_rgba(0,212,224,0.28),inset_0_1px_0_rgba(255,255,255,0.35)]"
                    : "border border-[var(--border)] bg-[var(--surface)] text-[var(--fg-muted)] shadow-[var(--shadow-card)] hover:text-[var(--fg)]",
                )}
                onClick={() => selectTab(t)}
              >
                <Icon className="h-4 w-4" aria-hidden />
                {t}
              </button>
            );
          })}
        </div>
      </div>

      {pageLoading ? (
        <DeskSkeleton rows={4} />
      ) : pageError ? (
        <DeskError message="Unable to load settings." onRetry={() => settingsQ.refetch()} />
      ) : (
        <div id="settings-panel" role="tabpanel" aria-labelledby={`settings-tab-${tab}`}>
        <PageMotion key={tab}>
          {tab === "Account" ? (
            <div className="grid grid-cols-1 items-stretch gap-4 lg:grid-cols-2">
              <SettingsDepthCard
                icon={<UserRound className="h-4 w-4" aria-hidden />}
                title="Profile Information"
                description="Your personal details and account identity."
                action={
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={() => document.getElementById("full-name")?.focus()}
                  >
                    <Pencil className="h-3.5 w-3.5" />
                    Edit Profile
                  </Button>
                }
              >
                <div className="mb-4 flex min-w-0 items-center gap-3">
                  <span className="inline-flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-[var(--accent)] text-base font-semibold text-[var(--accent-fg)] shadow-[0_10px_24px_rgba(0,212,224,0.28)]">
                    {initials}
                  </span>
                  <div className="min-w-0">
                    <p className="flex items-center gap-1.5 truncate text-base font-semibold text-[var(--fg)]">
                      {profileTitle}
                      {verified ? (
                        <span className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-[var(--success)] text-[10px] text-white" aria-label="Verified account">
                          ✓
                        </span>
                      ) : null}
                    </p>
                    <p className="truncate text-sm text-[var(--fg-muted)]">
                      {user?.email || "Email unavailable"}
                    </p>
                  </div>
                </div>
                <div className="grid flex-1 grid-cols-1 gap-3 sm:grid-cols-2">
                  <Field
                    id="full-name"
                    icon={<UserRound className="h-3.5 w-3.5" aria-hidden />}
                    label="Display Name"
                  >
                    <Input
                      id="full-name"
                      autoComplete="name"
                      value={profileForm.full_name}
                      onChange={(e) =>
                        setProfileForm((f) => ({ ...f, full_name: e.target.value }))
                      }
                    />
                  </Field>
                  <Field
                    id="username"
                    icon={<AtSign className="h-3.5 w-3.5" aria-hidden />}
                    label="Username"
                  >
                    <Input
                      id="username"
                      autoComplete="username"
                      value={profileForm.username}
                      onChange={(e) =>
                        setProfileForm((f) => ({ ...f, username: e.target.value }))
                      }
                    />
                  </Field>
                  <Field
                    id="account-email"
                    icon={<Mail className="h-3.5 w-3.5" aria-hidden />}
                    label="Email"
                  >
                    <Input id="account-email" value={user?.email || ""} readOnly />
                  </Field>
                  <Field
                    id="user-id"
                    icon={<Hash className="h-3.5 w-3.5" aria-hidden />}
                    label="User ID"
                  >
                    <div className="flex min-w-0 items-center gap-2">
                      <Input
                        id="user-id"
                        readOnly
                        inputMode="numeric"
                        value={shownUserId}
                        aria-label="User ID"
                      />
                      {shownUserId ? (
                        <Button
                          type="button"
                          size="icon"
                          variant="ghost"
                          aria-label="Copy user ID"
                          onClick={() => void copyText(shownUserId, "User ID")}
                        >
                          <Copy className="h-3.5 w-3.5" />
                        </Button>
                      ) : null}
                    </div>
                  </Field>
                </div>
              </SettingsDepthCard>

              <SettingsDepthCard
                icon={<SlidersHorizontal className="h-4 w-4" aria-hidden />}
                title="Trading Preferences"
                description="Set your default trading and execution options."
              >
                <div className="grid flex-1 grid-cols-1 content-start gap-3 sm:grid-cols-2">
                  <Field id="default-instrument" icon={<Coins className="h-3.5 w-3.5" aria-hidden />} label="Default Instrument">
                    <SelectBox id="default-instrument" value="XAUUSD" disabled onChange={() => undefined}>
                      <option value="XAUUSD">XAUUSD (Gold)</option>
                    </SelectBox>
                  </Field>
                  <Field id="default-lot" icon={<Hash className="h-3.5 w-3.5" aria-hidden />} label="Default Lot Size">
                    <SelectBox
                      id="default-lot"
                      value={displayPrefs.lot}
                      onChange={(value) => updateDisplay({ lot: value })}
                    >
                      {["0.01", "0.02", "0.05", "0.10"].map((lot) => (
                        <option key={lot} value={lot}>
                          {lot}
                        </option>
                      ))}
                    </SelectBox>
                  </Field>
                  <Field id="default-order-type" icon={<Zap className="h-3.5 w-3.5" aria-hidden />} label="Order Type (Default)">
                    <SelectBox
                      id="default-order-type"
                      value={displayPrefs.orderType}
                      onChange={(value) =>
                        updateDisplay({ orderType: value === "limit" ? "limit" : "market" })
                      }
                    >
                      <option value="market">Market</option>
                      <option value="limit">Limit</option>
                    </SelectBox>
                  </Field>
                  <Field id="max-slippage" icon={<SlidersHorizontal className="h-3.5 w-3.5" aria-hidden />} label="Slippage (Max)">
                    <SelectBox
                      id="max-slippage"
                      value={displayPrefs.slippage}
                      onChange={(value) => updateDisplay({ slippage: value })}
                    >
                      {["0.10", "0.50", "1.00"].map((value) => (
                        <option key={value} value={value}>
                          {value}
                        </option>
                      ))}
                    </SelectBox>
                  </Field>
                </div>
              </SettingsDepthCard>

              <SettingsDepthCard
                icon={<SettingsIcon className="h-4 w-4" aria-hidden />}
                title="Platform Preferences"
                description="Customize the platform behavior and trading experience."
              >
                <Toggle
                  label="Confirm before placing an order"
                  description="Show a confirmation dialog before executing trades"
                  checked={displayPrefs.confirmBeforeOrder}
                  onChange={(value) => updateDisplay({ confirmBeforeOrder: value })}
                />
                <Toggle
                  label="Show trading notifications"
                  description="Receive real-time trade and system alerts"
                  checked={settingsForm.notifications_enabled}
                  onChange={(value) =>
                    setSettingsForm((current) => ({ ...current, notifications_enabled: value }))
                  }
                />
                <Toggle
                  label="Enable advanced mode"
                  description="Unlock advanced trading controls and expert settings"
                  checked={displayPrefs.advancedMode}
                  onChange={(value) => updateDisplay({ advancedMode: value })}
                />
              </SettingsDepthCard>

              <SettingsDepthCard
                icon={<Clock className="h-4 w-4" aria-hidden />}
                title="Time & Display"
                description="Choose your time zone, date format, and number style."
              >
                <div className="grid flex-1 grid-cols-1 content-start gap-3 sm:grid-cols-2">
                  <Field id="timezone" icon={<Clock className="h-3.5 w-3.5" aria-hidden />} label="Time Zone">
                    <SelectBox
                      id="timezone"
                      value={profileForm.timezone}
                      onChange={(value) =>
                        setProfileForm((current) => ({ ...current, timezone: value }))
                      }
                    >
                      <option value="">Select timezone</option>
                      {zoneOptions.map((zone) => (
                        <option key={zone} value={zone}>
                          {zone}
                        </option>
                      ))}
                    </SelectBox>
                  </Field>
                  <Field id="date-format-account" icon={<Monitor className="h-3.5 w-3.5" aria-hidden />} label="Date Format">
                    <SelectBox
                      id="date-format-account"
                      value={deskPrefs.dateFormat}
                      onChange={(value) =>
                        setDeskPrefs((current) => ({
                          ...current,
                          dateFormat: value as DeskPreferencesV1["dateFormat"],
                        }))
                      }
                    >
                      {dateChoices.map((choice) => (
                        <option key={choice.value} value={choice.value}>
                          {choice.label}
                        </option>
                      ))}
                    </SelectBox>
                  </Field>
                  <Field id="number-format" icon={<Hash className="h-3.5 w-3.5" aria-hidden />} label="Number Format">
                    <SelectBox
                      id="number-format"
                      value={displayPrefs.numberFormat}
                      onChange={(value) =>
                        updateDisplay({ numberFormat: value === "dot" ? "dot" : "comma" })
                      }
                    >
                      <option value="comma">1,234.56</option>
                      <option value="dot">1.234,56</option>
                    </SelectBox>
                  </Field>
                  <Field id="theme" icon={<Monitor className="h-3.5 w-3.5" aria-hidden />} label="Theme">
                    <SelectBox id="theme" value="dark" disabled onChange={() => undefined}>
                      <option value="dark">Dark (Default)</option>
                    </SelectBox>
                  </Field>
                </div>
              </SettingsDepthCard>
            </div>
          ) : null}

          {tab === "Subscription" ? <SubscriptionPanel /> : null}

          {tab === "Security" ? (
            <div className="grid gap-4 lg:grid-cols-2">
              <Card className="qf-card-interactive">
                <CardHeader>
                  <CardTitle>Account protection</CardTitle>
                </CardHeader>
                <CardContent>
                  <Toggle
                    label="Login alerts"
                    description="Record a security email preference for new sign-ins."
                    checked={settingsForm.security_login_alerts}
                    onChange={(v) =>
                      setSettingsForm((f) => ({ ...f, security_login_alerts: v }))
                    }
                  />
                  <Toggle
                    label="Require re-authentication"
                    description="Ask for the password again before sensitive account changes."
                    checked={settingsForm.security_require_reauth}
                    onChange={(v) =>
                      setSettingsForm((f) => ({ ...f, security_require_reauth: v }))
                    }
                  />
                  <div className="space-y-1.5 pt-3">
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
                    <p className="text-xs text-[var(--fg-subtle)]">
                      Idle platform sessions end after this many minutes. Minimum 5.
                    </p>
                  </div>
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
                    At least 10 characters with uppercase, lowercase, a digit, and a symbol.
                    The current password is never shown.
                  </p>
                  <Button
                    variant="secondary"
                    disabled={changePw.isPending || !passwordOk}
                    onClick={() =>
                      setConfirm({
                        title: "Update password?",
                        body: "This replaces the password on your account. You will use the new password the next time you sign in.",
                        confirmLabel: "Update password",
                        action: () => changePw.mutate(),
                      })
                    }
                  >
                    {changePw.isPending ? "Updating…" : "Update password"}
                  </Button>
                </CardContent>
              </Card>

              <MfaSecurityPanel />

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
                        formatWhen(str(s.last_active_at, "—")),
                        <Button
                          key="r"
                          size="sm"
                          variant="ghost"
                          disabled={revoke.isPending}
                          onClick={() => {
                            const sessionId = str(s.id);
                            const ip = str(s.ip_address, "this address");
                            setConfirm({
                              title: "Revoke session?",
                              body: `The session from ${ip} will be signed out. This does not change your password.`,
                              confirmLabel: "Revoke session",
                              danger: true,
                              action: () => revoke.mutate(sessionId),
                            });
                          }}
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
                        str(d.label || d.device_name, "") ||
                          str(d.user_agent, "Device").slice(0, 64),
                        formatWhen(str(d.last_seen_at || d.last_active_at, "—")),
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
            <div className="grid gap-4">
              <Card className="qf-card-interactive">
                <CardHeader>
                  <CardTitle>Delivery</CardTitle>
                </CardHeader>
                <CardContent>
                  <Toggle
                    label="In-app notifications"
                    description="Show account alerts inside QuantForg."
                    checked={settingsForm.notifications_enabled}
                    onChange={(v) => setSettingsForm((f) => ({ ...f, notifications_enabled: v }))}
                  />
                  <Toggle
                    label="Security emails"
                    description="Email for sign-in and account protection events."
                    checked={settingsForm.email_security}
                    onChange={(v) => setSettingsForm((f) => ({ ...f, email_security: v }))}
                  />
                  <Toggle
                    label="Product emails"
                    description="Email for product and account updates."
                    checked={settingsForm.email_product}
                    onChange={(v) => setSettingsForm((f) => ({ ...f, email_product: v }))}
                  />
                  <Toggle
                    label="Marketing emails"
                    description="Optional product news."
                    checked={settingsForm.email_marketing}
                    onChange={(v) => setSettingsForm((f) => ({ ...f, email_marketing: v }))}
                  />
                  <p className="pt-3 text-xs text-[var(--fg-subtle)]">
                    Delivery choices are stored when you save changes.
                  </p>
                </CardContent>
              </Card>

              <Card className="qf-card-interactive">
                <CardHeader>
                  <CardTitle>Category channels</CardTitle>
                </CardHeader>
                <CardContent>
                  {prefsQ.isLoading ? (
                    <DeskSkeleton rows={3} />
                  ) : prefs.length === 0 ? (
                    <p className="text-sm text-[var(--fg-muted)]">
                      No category preferences are stored for this account yet.
                    </p>
                  ) : (
                    <ul>
                      {prefs.map((p) => {
                        const category = str(p.category);
                        const inApp = Boolean(p.in_app);
                        const email = Boolean(p.email);
                        return (
                          <li
                            key={category}
                            className="flex flex-col gap-3 border-b border-[var(--border)] py-3 last:border-0 sm:flex-row sm:items-center sm:justify-between"
                          >
                            <div className="min-w-0">
                              <p className="text-sm font-medium text-[var(--fg)]">
                                {labelize(category)}
                              </p>
                              <p className="text-xs text-[var(--fg-subtle)]">
                                Saved immediately for this category.
                              </p>
                            </div>
                            <div className="flex shrink-0 gap-2">
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
                </CardContent>
              </Card>
            </div>
          ) : null}

          {tab === "Preferences" ? (
            <div className="grid gap-4 lg:grid-cols-2">
              <Card className="qf-card-interactive">
                <CardHeader>
                  <CardTitle>Optional onboarding</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <p className="text-sm text-[var(--fg-muted)]">
                    New accounts land on Overview. The product guide is optional and never blocks
                    access.
                  </p>
                  <Button variant="secondary" asChild>
                    <Link href="/get-started">Open get-started guide</Link>
                  </Button>
                </CardContent>
              </Card>

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
                    Synced to your account. A local copy ({DESK_PREFS_KEY}) is kept for offline
                    fallback after a successful save.
                  </p>
                </CardContent>
              </Card>
            </div>
          ) : null}

          {tab === "Connections" ? (
            <div className="grid gap-4 lg:grid-cols-2">
              <Card className="qf-card-interactive">
                <CardHeader>
                  <div className="flex items-center justify-between gap-3">
                    <CardTitle>Broker</CardTitle>
                    <Badge tone="neutral">Open Broker desk</Badge>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  <p className="text-sm text-[var(--fg-muted)]">
                    Live gateway, MT5, and market-data status is shown on the Broker desk.
                    This page does not connect or change a broker.
                  </p>
                  <Button variant="secondary" asChild>
                    <Link href="/broker">Open Broker desk</Link>
                  </Button>
                </CardContent>
              </Card>

              <Card className="qf-card-interactive">
                <CardHeader>
                  <CardTitle>This account</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-sm">
                  <div className="flex items-center justify-between gap-3 border-b border-[var(--border)] pb-3">
                    <span className="text-[var(--fg-muted)]">Platform sessions</span>
                    <span className="font-medium text-[var(--fg)]">
                      {sessionsQ.isLoading ? "Loading" : sessionsQ.isError ? "Unavailable" : sessions.length}
                    </span>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-[var(--fg-muted)]">Known devices</span>
                    <span className="font-medium text-[var(--fg)]">
                      {devicesQ.isLoading ? "Loading" : devicesQ.isError ? "Unavailable" : devices.length}
                    </span>
                  </div>
                </CardContent>
              </Card>
            </div>
          ) : null}

          {tab === "Security" ? (
            <Card className="mt-4 border-[var(--danger)]/50">
              <CardHeader>
                <CardTitle className="text-[var(--danger)]">Danger Zone</CardTitle>
              </CardHeader>
              <CardContent className="divide-y divide-[var(--border)]">
                <div className="flex flex-col gap-3 py-4 first:pt-0 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="text-sm font-medium text-[var(--fg)]">Sign out</p>
                    <p className="text-sm text-[var(--fg-muted)]">
                      Ends this browser session and returns you to sign-in.
                    </p>
                  </div>
                  <Button
                    variant="secondary"
                    onClick={() =>
                      setConfirm({
                        title: "Sign out of this browser?",
                        body: "Your local session is cleared. Other devices stay signed in until you revoke them.",
                        confirmLabel: "Sign out",
                        danger: true,
                        action: () => {
                          void (async () => {
                            try {
                              await authApi.logout();
                            } catch {
                              /* still clear local session */
                            }
                            clearSession();
                            window.location.href = "/login";
                          })();
                        },
                      })
                    }
                  >
                    Sign out
                  </Button>
                </div>
                <div className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="text-sm font-medium text-[var(--fg)]">Revoke all sessions</p>
                    <p className="text-sm text-[var(--fg-muted)]">
                      Signs out every listed platform session, including this one.
                    </p>
                  </div>
                  <Button
                    variant="danger"
                    disabled={sessionsQ.isLoading || sessions.length === 0}
                    onClick={() =>
                      setConfirm({
                        title: "Revoke every session?",
                        body: "Each listed session is revoked. You may need to sign in again on this device.",
                        confirmLabel: "Revoke all sessions",
                        danger: true,
                        action: () => void revokeAllSessions(),
                      })
                    }
                  >
                    Revoke all sessions
                  </Button>
                </div>
                <div className="space-y-3 py-4 last:pb-0">
                  <div>
                    <p className="text-sm font-medium text-[var(--fg)]">Request account deletion</p>
                    <p className="text-sm text-[var(--fg-muted)]">
                      Sends a support ticket. The account is not deleted from this screen.
                    </p>
                  </div>
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
                    onClick={() =>
                      setConfirm({
                        title: "Submit a deletion request?",
                        body: "Support receives a ticket. Your account, positions, and billing stay unchanged until support processes it.",
                        confirmLabel: "Submit request",
                        danger: true,
                        action: () => requestDeletion.mutate(),
                      })
                    }
                  >
                    {requestDeletion.isPending ? "Submitting…" : "Submit deletion request"}
                  </Button>
                </div>
              </CardContent>
            </Card>
          ) : null}
        </PageMotion>
        </div>
      )}
      <Dialog open={confirm !== null} onOpenChange={(open) => { if (!open) setConfirm(null); }}>
        <DialogContent className="w-[min(92vw,28rem)]">
          <DialogTitle>{confirm?.title}</DialogTitle>
          <DialogDescription className="mt-2">{confirm?.body}</DialogDescription>
          <div className="mt-5 flex flex-wrap justify-end gap-2">
            <Button variant="secondary" onClick={() => setConfirm(null)}>
              Cancel
            </Button>
            <Button
              variant={confirm?.danger ? "danger" : "default"}
              onClick={() => {
                const action = confirm?.action;
                setConfirm(null);
                action?.();
              }}
            >
              {confirm?.confirmLabel ?? "Confirm"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function Toggle({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description?: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-[var(--border)] py-3 last:border-0">
      <div className="min-w-0">
        <p className="text-sm font-medium text-[var(--fg)]">{label}</p>
        {description ? <p className="text-xs text-[var(--fg-subtle)]">{description}</p> : null}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative h-6 w-11 shrink-0 rounded-full transition-colors duration-[var(--duration-fast)]",
          checked ? "bg-[var(--accent)]" : "bg-[var(--surface-3)]",
        )}
      >
        <span
          className={cn(
            "absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-transform duration-[var(--duration-fast)]",
            checked && "translate-x-5",
          )}
        />
      </button>
    </div>
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
      role="switch"
      aria-checked={checked}
      aria-label={`${label} ${checked ? "on" : "off"}`}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        "inline-flex h-9 items-center gap-2 rounded-full border px-3 text-xs font-medium",
        checked
          ? "border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent)]"
          : "border-[var(--border)] text-[var(--fg-muted)]",
        disabled && "opacity-60",
      )}
    >
      <span
        className={cn(
          "h-2 w-2 rounded-full",
          checked ? "bg-[var(--accent)]" : "bg-[var(--fg-subtle)]",
        )}
        aria-hidden
      />
      {label}
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

function SettingsDepthCard({
  icon,
  title,
  description,
  action,
  children,
}: {
  icon: ReactNode;
  title: string;
  description: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="flex h-full min-h-0 min-w-0 flex-col rounded-[22px] border border-[color-mix(in_srgb,var(--accent)_32%,var(--border))] bg-[var(--surface)] p-4 shadow-[0_16px_36px_rgba(2,12,28,0.28),inset_0_1px_0_rgba(255,255,255,0.07)] sm:p-5 lg:min-h-[22rem]">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[var(--accent-soft)] text-[var(--accent)] shadow-[inset_0_1px_0_rgba(255,255,255,0.2)]">
            {icon}
          </span>
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-[var(--fg)]">{title}</h2>
            <p className="mt-0.5 text-xs leading-relaxed text-[var(--fg-muted)]">{description}</p>
          </div>
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
      <div className="flex min-w-0 flex-1 flex-col">{children}</div>
    </section>
  );
}

function Field({
  id,
  icon,
  label,
  children,
}: {
  id?: string;
  icon: ReactNode;
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="min-w-0 space-y-1.5">
      <Label htmlFor={id} className="inline-flex items-center gap-1.5 text-[var(--fg-muted)]">
        {icon}
        {label}
      </Label>
      {children}
    </div>
  );
}

function SelectBox({
  id,
  value,
  disabled,
  onChange,
  children,
}: {
  id: string;
  value: string;
  disabled?: boolean;
  onChange: (value: string) => void;
  children: ReactNode;
}) {
  return (
    <select
      id={id}
      value={value}
      disabled={disabled}
      onChange={(event) => onChange(event.target.value)}
      className="flex h-11 w-full min-w-0 rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 text-sm text-[var(--fg)] shadow-[inset_0_1px_0_rgba(255,255,255,0.05)] disabled:opacity-80"
    >
      {children}
    </select>
  );
}
