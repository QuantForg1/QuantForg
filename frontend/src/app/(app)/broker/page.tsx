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
import { DeskSkeleton, DeskTable } from "@/components/desk/primitives";
import { RealtimeConnectionBadge } from "@/components/realtime/connection-badge";
import { Mt5BrokerDashboard } from "@/components/broker/mt5-dashboard";
import { ExecutionDiagnosticsPanel } from "@/components/execution/execution-diagnostics";
import { useBrokerStatusStream } from "@/hooks/realtime";
import { weltradeApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asRecord, num, str } from "@/lib/desk";
import {
  gatewayDiagnosticDetail,
  gatewayStatusLabel,
} from "@/lib/gateway-diagnostics";
import { useTradingSession } from "@/providers/trading-session-provider";
import { cn } from "@/lib/utils";

type AccountType = "demo" | "live";

const SECTIONS = [
  "Dashboard",
  "Broker",
  "Gateway",
  "Connection",
  "Synchronization",
  "Diagnostics",
  "Health",
  "Account",
  "Risk",
  "Market",
  "Positions",
  "Orders",
  "Trades",
  "Timeline",
] as const;

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

function Section({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <motion.section
      id={id}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="scroll-mt-24 rounded-2xl border border-[var(--border)] bg-[var(--surface)]/90 p-5 shadow-[var(--shadow-card)]"
    >
      <h2 className="mb-4 text-sm font-medium tracking-wide text-[var(--fg)]">{title}</h2>
      {children}
    </motion.section>
  );
}

export default function BrokerWorkspacePage() {
  const qc = useQueryClient();
  const session = useTradingSession();
  const realtime = useBrokerStatusStream(true);

  const healthQ = useQuery({
    queryKey: ["weltrade-health"],
    queryFn: weltradeApi.health,
    staleTime: 15_000,
    retry: 2,
  });
  const dash = useQuery({
    queryKey: ["weltrade-dashboard"],
    queryFn: weltradeApi.dashboard,
    staleTime: 12_000,
    retry: 2,
  });

  const connection = asRecord(asRecord(dash.data).connection);
  const account = asRecord(asRecord(dash.data).account);
  const profile = asRecord(asRecord(dash.data).profile);
  const health = asRecord(healthQ.data);
  const dashBody = asRecord(dash.data);
  const configuration = asRecord(health.configuration || dashBody.configuration);

  const connected = session.connected || Boolean(
    connection.mt5_connected || health.mt5_connected || health.mt5_attached,
  );
  const gatewayOnline =
    session.gatewayOnline ||
    Boolean(connection.gateway_online || health.gateway_online || health.gateway_reachable);
  const brokerConnected =
    session.brokerConnected ||
    Boolean(connection.weltrade_connected || health.weltrade_connected);

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
  const [activeNav, setActiveNav] = useState<(typeof SECTIONS)[number]>("Dashboard");

  const serverOptions = useMemo(() => {
    const servers = asRecord(profile.servers);
    const list = Array.isArray(servers[accountType])
      ? (servers[accountType] as string[])
      : [];
    return list.length > 0
      ? list
      : accountType === "demo"
        ? ["Weltrade-Demo"]
        : ["Weltrade-Real"];
  }, [profile.servers, accountType]);

  useEffect(() => {
    if (serverMode === "auto") {
      setServer("auto");
    } else if (!serverOptions.includes(server)) {
      setServer(serverOptions[0] ?? "Weltrade-Real");
    }
  }, [serverMode, serverOptions, server]);

  const refresh = async () => {
    await session.invalidateAll();
  };

  const connectMut = useMutation({
    mutationFn: weltradeApi.connect,
    onMutate: () => setProgress("Checking gateway…"),
    onSuccess: async (data) => {
      setProgress("Synchronizing account…");
      setPassword("");
      const body = asRecord(asRecord(data).dashboard);
      if (Object.keys(body).length > 0) {
        qc.setQueryData(["weltrade-dashboard"], body);
      }
      toast.success("Broker session attached");
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
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Disconnect failed"),
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
      if (!wasConnected) {
        toast.error(e instanceof ApiError ? e.message : "Reconnect failed");
      }
    },
  });

  const busy =
    connectMut.isPending || disconnectMut.isPending || reconnectMut.isPending;

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
    // eslint-disable-next-line react-hooks/exhaustive-deps -- recovery trigger
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

  const positions = session.positions;
  const orders = session.orders;
  const deals = session.historyDeals;
  const floating = num(session.profit, num(account.profit, 0));

  return (
    <div className="relative mx-auto max-w-6xl">
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
        className="relative mb-6"
      >
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-[var(--border)] bg-[var(--surface)] shadow-[var(--shadow-card)]">
              <span className="font-display text-lg tracking-tight text-[var(--accent)]">
                QF
              </span>
            </div>
            <div>
              <p className="font-display text-2xl tracking-tight text-[var(--fg)] sm:text-3xl">
                Broker Workspace
              </p>
              <p className="mt-1 text-sm text-[var(--fg-muted)]">
                Live MT5 dashboard — account, book, quotes, and session control
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <RealtimeConnectionBadge status={realtime} />
            <Badge tone={connected ? "success" : gatewayOnline ? "warning" : "neutral"}>
              {connected ? "Connected" : gatewayOnline ? "Gateway ready" : "Offline"}
            </Badge>
            <Button
              size="sm"
              variant="ghost"
              disabled={session.refreshing || dash.isFetching}
              onClick={() => void refresh()}
            >
              <RefreshCw
                className={cn(
                  "h-3.5 w-3.5",
                  (session.refreshing || dash.isFetching) && "animate-spin",
                )}
              />
              Sync all
            </Button>
          </div>
        </div>

        <nav
          className="mt-5 flex gap-1 overflow-x-auto pb-1"
          aria-label="Broker workspace sections"
        >
          {SECTIONS.map((s) => (
            <a
              key={s}
              href={`#bw-${s.toLowerCase()}`}
              onClick={() => setActiveNav(s)}
              className={cn(
                "shrink-0 rounded-md px-2.5 py-1.5 text-[11px] uppercase tracking-[0.12em] transition",
                activeNav === s
                  ? "bg-[var(--accent-soft)] text-[var(--fg)]"
                  : "text-[var(--fg-subtle)] hover:text-[var(--fg-muted)]",
              )}
            >
              {s}
            </a>
          ))}
        </nav>
      </motion.header>

      {dash.isLoading && healthQ.isLoading && !session.login ? (
        <DeskSkeleton rows={8} />
      ) : (
        <div className="relative space-y-5">
          <Mt5BrokerDashboard />

          <ExecutionDiagnosticsPanel />

          <Section id="bw-broker" title="Broker">
            <div className="grid gap-3 sm:grid-cols-3">
              <StatusDot on={gatewayOnline} label={gatewayLabel} />
              <StatusDot
                on={connected}
                label={connected ? "MT5 Session Attached" : "MT5 Not Attached"}
              />
              <StatusDot
                on={brokerConnected}
                label={brokerConnected ? "Broker Connected" : "Broker Idle"}
              />
            </div>
          </Section>

          <Section id="bw-gateway" title="Gateway">
            <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
              <Metric label="Status" value={gatewayOnline ? "Online" : "Offline"} />
              <Metric
                label="Latency"
                value={
                  session.latencyMs !== "—"
                    ? `${session.latencyMs} ms`
                    : connection.latency_ms != null
                      ? `${str(connection.latency_ms)} ms`
                      : "—"
                }
              />
              <Metric
                label="Base URL"
                value={str(
                  health.gateway_url || configuration.mt5_gateway_base_url,
                  "—",
                ).replace(/^https?:\/\//, "")}
              />
              <Metric
                label="HTTP"
                value={
                  health.last_http_status != null
                    ? String(health.last_http_status)
                    : "—"
                }
              />
            </div>
            {!gatewayOnline && upstreamDetail && upstreamDetail !== "ok" ? (
              <p className="mt-3 break-words font-mono text-xs text-[var(--fg)]">
                {upstreamDetail}
              </p>
            ) : null}
          </Section>

          <div className="grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
            <Section id="bw-connection" title="Connection">
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
                <Label htmlFor="bw-login">Login</Label>
                <Input
                  id="bw-login"
                  inputMode="numeric"
                  autoComplete="username"
                  value={login}
                  onChange={(e) => setLogin(e.target.value)}
                  placeholder="Account number"
                />
              </div>
              <div className="mb-4 space-y-2">
                <Label htmlFor="bw-password">Password</Label>
                <Input
                  id="bw-password"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Only if terminal is not already logged in"
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
                  Remember on the local gateway only — never stored in the browser,
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
            </Section>

            <div className="space-y-5">
              <Section id="bw-diagnostics" title="Diagnostics">
                <div className="mb-2 flex items-center gap-2 text-[var(--accent)]">
                  <Activity className="h-4 w-4" />
                  <span className="text-xs uppercase tracking-[0.14em]">Transport</span>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <Metric
                    label="Latency"
                    value={
                      session.latencyMs !== "—"
                        ? `${session.latencyMs} ms`
                        : "—"
                    }
                  />
                  <Metric
                    label="Heartbeat"
                    value={(session.heartbeatAt || str(connection.heartbeat_at, "—"))
                      .replace("T", " ")
                      .slice(0, 19)}
                  />
                  <Metric label="Session mode" value={str(connection.session_mode, "none")} />
                  <Metric label="Login status" value={session.loginStatus} />
                </div>
                <div className="mt-4">
                  <ExecutionDiagnosticsPanel dense />
                </div>
              </Section>

              <Section id="bw-health" title="Health">
                <div className="grid grid-cols-2 gap-2">
                  <Metric label="Gateway" value={gatewayOnline ? "Healthy" : "Degraded"} />
                  <Metric label="MT5" value={connected ? "Healthy" : "Idle"} />
                  <Metric label="Realtime" value={realtime.connected ? "Synced" : "Polling"} />
                  <Metric
                    label="Redirects"
                    value={
                      health.redirects_followed != null
                        ? String(health.redirects_followed)
                        : "—"
                    }
                  />
                </div>
              </Section>
            </div>
          </div>

          <Section id="bw-synchronization" title="Synchronization">
            <div className="grid grid-cols-2 gap-2 md:grid-cols-4 lg:grid-cols-6">
              <Metric label="Positions" value={String(positions.length)} />
              <Metric label="Orders" value={String(orders.length)} />
              <Metric label="Recent deals" value={String(deals.length)} />
              <Metric
                label="Last sync"
                value={str(connection.last_sync_at, "live").replace("T", " ").slice(0, 19)}
              />
              <Metric label="Refreshing" value={session.refreshing ? "yes" : "no"} />
              <Metric label="Source" value="Trading Session" />
            </div>
          </Section>

          <div className="grid gap-5 lg:grid-cols-2">
            <Section id="bw-account" title="Account Information">
              {connected ? (
                <div className="grid grid-cols-2 gap-2">
                  <Metric label="Login" value={session.login} />
                  <Metric label="Name" value={str(account.name, "—")} />
                  <Metric label="Server" value={session.server} />
                  <Metric label="Currency" value={session.currency || "—"} />
                  <Metric label="Balance" value={session.balance} />
                  <Metric label="Equity" value={session.equity} />
                  <Metric label="Leverage" value={session.leverage} />
                  <Metric label="Company" value={str(account.company, "Broker")} />
                </div>
              ) : (
                <p className="text-sm text-[var(--fg-muted)]">
                  Attach the live session to populate account fields from MT5.
                </p>
              )}
            </Section>

            <Section id="bw-risk" title="Risk Information">
              {connected ? (
                <div className="grid grid-cols-2 gap-2">
                  <Metric label="Margin" value={session.margin} />
                  <Metric label="Free margin" value={session.freeMargin} />
                  <Metric label="Margin level" value={session.marginLevel} />
                  <Metric
                    label="Floating P/L"
                    value={Number.isFinite(floating) ? String(floating) : session.profit}
                  />
                </div>
              ) : (
                <p className="text-sm text-[var(--fg-muted)]">
                  Risk metrics appear once margin data syncs from the attached terminal.
                </p>
              )}
            </Section>
          </div>

          <div className="grid gap-5 lg:grid-cols-2">
            <Section id="bw-market" title="Market Status">
              <div className="grid grid-cols-2 gap-2">
                <Metric label="Session" value={connected ? "Live quotes" : "Offline"} />
                <Metric label="Watch source" value="Connected broker" />
                <Metric label="Terminal" value={str(connection.broker_version, "MT5")} />
                <Metric label="Trade mode" value={str(account.trade_mode, "—")} />
              </div>
            </Section>

            <Section id="bw-sync-note" title="Live sync">
              <p className="text-sm text-[var(--fg-muted)]">
                Account, positions, orders, and deal history refresh automatically via the
                MT5 book stream. Quote widgets poll {connected ? "every 3s" : "when attached"}.
              </p>
            </Section>
          </div>

          <Section id="bw-positions" title="Open Positions">
            {positions.length === 0 ? (
              <p className="text-sm text-[var(--fg-muted)]">No open positions</p>
            ) : (
              <DeskTable
                columns={["Symbol", "Side", "Volume", "Open", "SL", "TP", "P/L"]}
                rows={positions.slice(0, 20).map((p) => [
                  str(p.symbol),
                  str(p.side),
                  str(p.volume),
                  str(p.open_price),
                  str(p.stop_loss ?? p.sl, "—"),
                  str(p.take_profit ?? p.tp, "—"),
                  str(p.profit),
                ])}
              />
            )}
          </Section>

          <Section id="bw-orders" title="Pending Orders">
            {orders.length === 0 ? (
              <p className="text-sm text-[var(--fg-muted)]">No pending orders</p>
            ) : (
              <DeskTable
                columns={["Symbol", "Type", "Volume", "Price"]}
                rows={orders.slice(0, 20).map((o) => [
                  str(o.symbol),
                  str(o.order_type || o.type),
                  str(o.volume),
                  str(o.price),
                ])}
              />
            )}
          </Section>

          <Section id="bw-trades" title="Recent Trades">
            <div className="mb-3">
              <a
                href="/journal/orders"
                className="text-xs text-[var(--accent)] underline-offset-2 hover:underline"
              >
                Open full Orders History →
              </a>
            </div>
            {deals.length === 0 ? (
              <p className="text-sm text-[var(--fg-muted)]">No completed trades</p>
            ) : (
              <DeskTable
                columns={["Symbol", "Side", "Volume", "Profit", "Time"]}
                rows={deals.slice(0, 20).map((d) => [
                  str(d.symbol),
                  str(d.side || d.deal_type, "—"),
                  str(d.volume),
                  str(d.profit),
                  str(d.time, "—").replace("T", " ").slice(0, 19),
                ])}
              />
            )}
          </Section>

          <Section id="bw-timeline" title="Connection Timeline">
            <ul className="space-y-2 text-sm text-[var(--fg-muted)]">
              <li className="flex items-center gap-2">
                <Shield className="h-3.5 w-3.5 text-[var(--accent)]" />
                Gateway: {gatewayOnline ? "reachable" : "unreachable"}
              </li>
              <li className="flex items-center gap-2">
                <Cable className="h-3.5 w-3.5 text-[var(--accent)]" />
                Session: {connected ? "attached" : "detached"}
              </li>
              <li className="flex items-center gap-2">
                <Activity className="h-3.5 w-3.5 text-[var(--accent)]" />
                Heartbeat:{" "}
                {(session.heartbeatAt || str(connection.heartbeat_at, "—"))
                  .replace("T", " ")
                  .slice(0, 19)}
              </li>
              <li className="flex items-center gap-2">
                <RefreshCw className="h-3.5 w-3.5 text-[var(--accent)]" />
                Auto-reconnect: {wasConnected ? "armed" : "idle"}
              </li>
            </ul>
          </Section>
        </div>
      )}
    </div>
  );
}
