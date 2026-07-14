"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";
import {
  Activity,
  Cable,
  CheckCircle2,
  Circle,
  Loader2,
  RefreshCw,
  Shield,
  Unplug,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { DeskSkeleton } from "@/components/desk/primitives";
import { RealtimeConnectionBadge } from "@/components/realtime/connection-badge";
import { useBrokerStatusStream } from "@/hooks/realtime";
import { weltradeApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asRecord, str } from "@/lib/desk";
import {
  gatewayDiagnosticDetail,
  gatewayStatusLabel,
} from "@/lib/gateway-diagnostics";
import { cn } from "@/lib/utils";

type AccountType = "demo" | "live";

function StatusDot({ on, label }: { on: boolean; label: string }) {
  return (
    <div className="flex items-center gap-2 text-sm">
      {on ? (
        <CheckCircle2 className="h-4 w-4 text-[var(--success)]" aria-hidden />
      ) : (
        <Circle className="h-4 w-4 text-[var(--fg-subtle)]" aria-hidden />
      )}
      <span className={on ? "text-[var(--fg)]" : "text-[var(--fg-muted)]"}>{label}</span>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)]/80 px-3 py-3">
      <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--fg-subtle)]">{label}</p>
      <p className="mt-1 font-mono text-sm tabular text-[var(--fg)]">{value}</p>
    </div>
  );
}

export default function WeltradeBrokerPage() {
  const qc = useQueryClient();
  const realtime = useBrokerStatusStream(true);
  const healthQ = useQuery({
    queryKey: ["weltrade-health"],
    queryFn: weltradeApi.health,
    refetchInterval: 5_000,
    retry: 2,
  });
  const dash = useQuery({
    queryKey: ["weltrade-dashboard"],
    queryFn: weltradeApi.dashboard,
    refetchInterval: 8_000,
    retry: 2,
  });

  const connection = asRecord(asRecord(dash.data).connection);
  const account = asRecord(asRecord(dash.data).account);
  const profile = asRecord(asRecord(dash.data).profile);
  const positions = asRecord(asRecord(dash.data).positions);
  const orders = asRecord(asRecord(dash.data).orders);
  const history = asRecord(asRecord(dash.data).history);
  const health = asRecord(healthQ.data);
  const dashBody = asRecord(dash.data);
  const configuration = asRecord(health.configuration || dashBody.configuration);

  const connected = Boolean(
    connection.mt5_connected || health.mt5_connected || health.mt5_attached,
  );
  const gatewayOnline = Boolean(
    connection.gateway_online || health.gateway_online || health.gateway_reachable,
  );
  const weltradeConnected = Boolean(
    connection.weltrade_connected || health.weltrade_connected,
  );
  const upstreamDetail = gatewayDiagnosticDetail({
    ...health,
    ...dashBody,
    last_upstream_error:
      health.last_upstream_error || dashBody.last_upstream_error,
    upstream_error: health.upstream_error || dashBody.upstream_error,
    detail: health.detail || dashBody.detail,
    diagnostic: health.diagnostic || dashBody.diagnostic,
  });
  const gatewayLabel = gatewayOnline
    ? "Gateway Online"
    : gatewayStatusLabel({
        ...health,
        ...dashBody,
        gateway_online: gatewayOnline,
        diagnostic: health.diagnostic || dashBody.diagnostic,
        last_upstream_error: upstreamDetail,
        detail: upstreamDetail,
      });

  const [accountType, setAccountType] = useState<AccountType>("demo");
  const [serverMode, setServerMode] = useState<"auto" | "manual">("auto");
  const [server, setServer] = useState("auto");
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [rememberGateway, setRememberGateway] = useState(true);
  const [progress, setProgress] = useState<string | null>(null);
  const [wasConnected, setWasConnected] = useState(false);
  const recoveringRef = useRef(false);

  const serverOptions = useMemo(() => {
    const servers = asRecord(profile.servers);
    const list = Array.isArray(servers[accountType]) ? (servers[accountType] as string[]) : [];
    return list.length > 0 ? list : accountType === "demo" ? ["Weltrade-Demo"] : ["Weltrade-MT5"];
  }, [profile.servers, accountType]);

  useEffect(() => {
    if (serverMode === "auto") {
      setServer("auto");
    } else if (!serverOptions.includes(server)) {
      setServer(serverOptions[0] ?? "Weltrade-MT5");
    }
  }, [serverMode, serverOptions, server]);

  const refresh = async () => {
    await Promise.all([
      qc.invalidateQueries({ queryKey: ["weltrade-dashboard"] }),
      qc.invalidateQueries({ queryKey: ["weltrade-health"] }),
      qc.invalidateQueries({ queryKey: ["mt5-status"] }),
      qc.invalidateQueries({ queryKey: ["portfolio"] }),
      qc.invalidateQueries({ queryKey: ["orders"] }),
      qc.invalidateQueries({ queryKey: ["positions"] }),
      qc.invalidateQueries({ queryKey: ["history"] }),
      qc.invalidateQueries({ queryKey: ["mt5-symbols"] }),
      qc.invalidateQueries({ queryKey: ["brokers"] }),
    ]);
  };

  const connectMut = useMutation({
    mutationFn: weltradeApi.connect,
    onMutate: () => setProgress("Checking gateway…"),
    onSuccess: async (data) => {
      setProgress("Synchronizing account…");
      setPassword("");
      const dashBody = asRecord(asRecord(data).dashboard);
      if (Object.keys(dashBody).length > 0) {
        qc.setQueryData(["weltrade-dashboard"], dashBody);
      }
      toast.success("Weltrade connected");
      await refresh();
      setProgress(null);
      setWasConnected(true);
    },
    onError: (e) => {
      setProgress(null);
      toast.error(e instanceof ApiError ? e.message : "Connection failed");
    },
  });

  const disconnectMut = useMutation({
    mutationFn: weltradeApi.disconnect,
    onSuccess: async () => {
      toast.success("Disconnected");
      setWasConnected(false);
      await refresh();
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Disconnect failed"),
  });

  const reconnectMut = useMutation({
    mutationFn: weltradeApi.reconnect,
    onMutate: () => setProgress("Reconnecting…"),
    onSuccess: async () => {
      toast.success("Session restored");
      await refresh();
      setProgress(null);
      setWasConnected(true);
    },
    onError: (e) => {
      setProgress(null);
      // Silent retry path — avoid toast spam during auto-recovery
      if (!wasConnected) {
        toast.error(e instanceof ApiError ? e.message : "Reconnect failed");
      }
    },
  });

  const busy = connectMut.isPending || disconnectMut.isPending || reconnectMut.isPending;

  // Automatic recovery: if we had a live session and it drops, reconnect quietly.
  useEffect(() => {
    if (connected) {
      setWasConnected(true);
      recoveringRef.current = false;
      return;
    }
    if (!wasConnected || !gatewayOnline) return;
    if (busy || recoveringRef.current) return;
    recoveringRef.current = true;
    const t = window.setTimeout(() => {
      reconnectMut.mutate(undefined, {
        onSettled: () => {
          recoveringRef.current = false;
        },
      });
    }, 1500);
    return () => window.clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- intentional recovery trigger
  }, [connected, gatewayOnline, wasConnected, busy]);

  const onConnect = () => {
    const loginNum = Number(login);
    if (!Number.isFinite(loginNum) || loginNum <= 0) {
      toast.error("Enter a valid login");
      return;
    }
    setProgress("Validating…");
    connectMut.mutate({
      login: loginNum,
      password,
      server: serverMode === "auto" ? "auto" : server,
      account_type: accountType,
      prefer_attach: true,
      remember_on_gateway: rememberGateway,
    });
  };

  return (
    <div className="relative mx-auto max-w-5xl">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 -top-8 h-56 opacity-70"
        style={{
          background:
            "radial-gradient(ellipse 70% 80% at 20% 0%, color-mix(in srgb, var(--accent) 22%, transparent), transparent 70%), radial-gradient(ellipse 50% 60% at 90% 10%, rgba(255,255,255,0.04), transparent 65%)",
        }}
      />

      <motion.header
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative mb-8"
      >
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-[var(--border)] bg-[var(--surface)] shadow-[var(--shadow-card)]">
              <span className="font-display text-lg tracking-tight text-[var(--accent)]">W</span>
            </div>
            <div>
              <p className="font-display text-2xl tracking-tight text-[var(--fg)] sm:text-3xl">
                Broker Connection
              </p>
              <p className="mt-1 text-sm text-[var(--fg-muted)]">
                Weltrade MT5 — connection, account, sync, and diagnostics
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <RealtimeConnectionBadge status={realtime} />
            <Badge tone={connected ? "success" : gatewayOnline ? "warning" : "neutral"}>
              {connected ? "Connected" : gatewayOnline ? "Gateway ready" : "Offline"}
            </Badge>
          </div>
        </div>
      </motion.header>

      {dash.isLoading && healthQ.isLoading ? (
        <DeskSkeleton rows={6} />
      ) : (
        <div className="relative space-y-6">
          <motion.section
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-2xl border border-[var(--border)] bg-[var(--surface)]/90 p-5 shadow-[var(--shadow-card)]"
          >
            <div className="mb-4 flex items-center justify-between gap-3">
              <h2 className="text-sm font-medium tracking-wide text-[var(--fg)]">Connection Status</h2>
              <Button
                size="sm"
                variant="ghost"
                disabled={dash.isFetching || healthQ.isFetching}
                onClick={() => {
                  void dash.refetch();
                  void healthQ.refetch();
                }}
              >
                <RefreshCw
                  className={cn(
                    "h-3.5 w-3.5",
                    (dash.isFetching || healthQ.isFetching) && "animate-spin",
                  )}
                />
                Refresh
              </Button>
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <StatusDot on={gatewayOnline} label={gatewayLabel} />
              <StatusDot on={connected} label={connected ? "MT5 Connected" : "MT5 Not Connected"} />
              <StatusDot
                on={weltradeConnected}
                label={weltradeConnected ? "Weltrade Connected" : "Weltrade Not Connected"}
              />
            </div>
            {!gatewayOnline && upstreamDetail && upstreamDetail !== "ok" ? (
              <div className="mt-4 rounded-lg border border-[var(--danger-border,var(--border))] bg-[var(--surface-2)] px-3 py-3 text-sm text-[var(--fg-muted)]">
                <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
                  {gatewayLabel}
                </p>
                <p className="mt-1 break-words font-mono text-xs text-[var(--fg)]">
                  {upstreamDetail}
                </p>
                {str(health.gateway_url || configuration.mt5_gateway_base_url) ? (
                  <p className="mt-2 text-[11px] text-[var(--fg-subtle)]">
                    Base URL: {str(health.gateway_url || configuration.mt5_gateway_base_url)}
                  </p>
                ) : null}
                {health.last_http_status != null ? (
                  <p className="mt-1 text-[11px] text-[var(--fg-subtle)]">
                    HTTP {str(health.last_http_status)}
                    {health.redirects_followed != null
                      ? ` · redirects ${str(health.redirects_followed)}`
                      : ""}
                    {health.latency != null || health.latency_ms != null
                      ? ` · ${str(health.latency ?? health.latency_ms)} ms`
                      : ""}
                  </p>
                ) : null}
              </div>
            ) : null}
          </motion.section>

          <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
            <motion.section
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.05 }}
              className="rounded-2xl border border-[var(--border)] bg-[var(--surface)]/90 p-5 shadow-[var(--shadow-card)]"
            >
              <h2 className="mb-4 text-sm font-medium text-[var(--fg)]">Account</h2>

              <div className="mb-4">
                <Label className="mb-2 block">Account Type</Label>
                <div className="grid grid-cols-2 gap-2">
                  {(["demo", "live"] as const).map((t) => (
                    <button
                      key={t}
                      type="button"
                      onClick={() => setAccountType(t)}
                      className={cn(
                        "rounded-lg border px-3 py-2 text-sm capitalize transition",
                        accountType === t
                          ? "border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--fg)]"
                          : "border-[var(--border)] text-[var(--fg-muted)] hover:border-[var(--border-strong)]",
                      )}
                    >
                      {t}
                    </button>
                  ))}
                </div>
              </div>

              <div className="mb-4 space-y-2">
                <Label>Server</Label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setServerMode("auto")}
                    className={cn(
                      "rounded-lg border px-3 py-2 text-sm transition",
                      serverMode === "auto"
                        ? "border-[var(--accent)] bg-[var(--accent-soft)]"
                        : "border-[var(--border)] text-[var(--fg-muted)]",
                    )}
                  >
                    Auto Detect
                  </button>
                  <button
                    type="button"
                    onClick={() => setServerMode("manual")}
                    className={cn(
                      "rounded-lg border px-3 py-2 text-sm transition",
                      serverMode === "manual"
                        ? "border-[var(--accent)] bg-[var(--accent-soft)]"
                        : "border-[var(--border)] text-[var(--fg-muted)]",
                    )}
                  >
                    Manual
                  </button>
                </div>
                {serverMode === "manual" && (
                  <select
                    className="mt-2 h-10 w-full rounded-md border border-[var(--border)] bg-[var(--surface-2)] px-3 text-sm text-[var(--fg)]"
                    value={server}
                    onChange={(e) => setServer(e.target.value)}
                  >
                    {serverOptions.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                )}
              </div>

              <div className="mb-3 space-y-2">
                <Label htmlFor="wt-login">Login</Label>
                <Input
                  id="wt-login"
                  inputMode="numeric"
                  autoComplete="username"
                  value={login}
                  onChange={(e) => setLogin(e.target.value)}
                  placeholder="Weltrade account number"
                />
              </div>
              <div className="mb-4 space-y-2">
                <Label htmlFor="wt-password">Password</Label>
                <Input
                  id="wt-password"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Required only if terminal is not logged in"
                />
              </div>

              <label className="mb-5 flex cursor-pointer items-start gap-2 text-sm text-[var(--fg-muted)]">
                <input
                  type="checkbox"
                  className="mt-1"
                  checked={rememberGateway}
                  onChange={(e) => setRememberGateway(e.target.checked)}
                />
                <span>
                  Remember this account on the local gateway only — never stored in the browser,
                  Railway, or the database.
                </span>
              </label>

              <div className="flex flex-wrap gap-2">
                <Button disabled={busy} onClick={onConnect}>
                  {connectMut.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Cable className="h-4 w-4" />
                  )}
                  Connect
                </Button>
                <Button
                  variant="secondary"
                  disabled={busy || !connected}
                  onClick={() => disconnectMut.mutate()}
                >
                  <Unplug className="h-4 w-4" />
                  Disconnect
                </Button>
                <Button
                  variant="outline"
                  disabled={busy}
                  onClick={() => reconnectMut.mutate()}
                >
                  <RefreshCw className="h-4 w-4" />
                  Reconnect
                </Button>
              </div>

              <AnimatePresence>
                {progress && (
                  <motion.p
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    className="mt-4 flex items-center gap-2 text-sm text-[var(--accent)]"
                  >
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    {progress}
                  </motion.p>
                )}
              </AnimatePresence>
            </motion.section>

            <motion.section
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.08 }}
              className="space-y-6"
            >
              <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)]/90 p-5 shadow-[var(--shadow-card)]">
                <div className="mb-4 flex items-center gap-2">
                  <Activity className="h-4 w-4 text-[var(--accent)]" />
                  <h2 className="text-sm font-medium text-[var(--fg)]">Connection Diagnostics</h2>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <Metric
                    label="Latency"
                    value={
                      connection.latency_ms != null ? `${str(connection.latency_ms)} ms` : "—"
                    }
                  />
                  <Metric
                    label="Heartbeat"
                    value={str(connection.heartbeat_at, "—").replace("T", " ").slice(0, 19)}
                  />
                  <Metric label="Gateway" value={gatewayOnline ? "Online" : "Offline"} />
                  <Metric label="MT5" value={connected ? "Connected" : "Idle"} />
                  <Metric label="Session" value={str(connection.session_mode, "none")} />
                  <Metric label="Version" value={str(connection.broker_version, "—")} />
                </div>
              </div>

              <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)]/90 p-5 shadow-[var(--shadow-card)]">
                <div className="mb-4 flex items-center gap-2">
                  <Shield className="h-4 w-4 text-[var(--accent)]" />
                  <h2 className="text-sm font-medium text-[var(--fg)]">Recent Synchronization</h2>
                </div>
                {connected && !account.error ? (
                  <div className="grid grid-cols-2 gap-2">
                    <Metric label="Account" value={str(account.login, "—")} />
                    <Metric label="Name" value={str(account.name, "—")} />
                    <Metric label="Server" value={str(account.server ?? connection.server, "—")} />
                    <Metric label="Leverage" value={str(account.leverage, "—")} />
                    <Metric label="Balance" value={str(account.balance, "—")} />
                    <Metric label="Equity" value={str(account.equity, "—")} />
                    <Metric label="Margin" value={str(account.margin, "—")} />
                    <Metric label="Free Margin" value={str(account.free_margin, "—")} />
                    <Metric label="Positions" value={str(positions.count, "0")} />
                    <Metric label="Orders" value={str(orders.count, "0")} />
                    <Metric label="History" value={str(history.count, "0")} />
                    <Metric
                      label="Last Sync"
                      value={str(connection.last_sync_at, "—").replace("T", " ").slice(0, 19)}
                    />
                  </div>
                ) : (
                  <p className="text-sm text-[var(--fg-muted)]">
                    Connect Weltrade to synchronize balance, equity, margin, positions, and history.
                  </p>
                )}
              </div>
            </motion.section>
          </div>
        </div>
      )}
    </div>
  );
}
