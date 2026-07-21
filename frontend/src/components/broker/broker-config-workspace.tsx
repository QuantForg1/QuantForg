"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Cable,
  CheckCircle2,
  Circle,
  Loader2,
  RefreshCw,
  Unplug,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DeskSkeleton } from "@/components/desk/primitives";
import { mt5Api, weltradeApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asRecord, str } from "@/lib/desk";
import { TRADING_SYMBOL } from "@/lib/trading/gold-only";
import { useTradingSession } from "@/providers/trading-session-provider";
import { cn } from "@/lib/utils";

type AccountType = "demo" | "live";

function Diag({ ok, label }: { ok: boolean | null; label: string }) {
  const tone =
    ok === true ? "text-[var(--success)]" : ok === false ? "text-[var(--fg-muted)]" : "text-[var(--fg-subtle)]";
  return (
    <div className="flex items-center gap-2 border border-[var(--border)] bg-[var(--bg)]/30 px-3 py-2.5">
      {ok === true ? (
        <CheckCircle2 className={cn("h-3.5 w-3.5 shrink-0", tone)} aria-hidden />
      ) : (
        <Circle className={cn("h-3.5 w-3.5 shrink-0", tone)} aria-hidden />
      )}
      <span className="text-sm text-[var(--fg)]">{label}</span>
      <span className={cn("ml-auto font-mono text-[10px] uppercase", tone)}>
        {ok === true ? "OK" : ok === false ? "NO" : "—"}
      </span>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-[var(--border)] bg-[var(--bg)]/30 px-3 py-2.5">
      <p className="text-[9px] uppercase tracking-[0.14em] text-[var(--fg-subtle)]">{label}</p>
      <p className="mt-1 truncate font-mono text-sm tabular text-[var(--fg)]">{value}</p>
    </div>
  );
}

function Section({
  title,
  children,
  aside,
}: {
  title: string;
  children: React.ReactNode;
  aside?: React.ReactNode;
}) {
  return (
    <section className="border border-[var(--border)] bg-[var(--surface)]">
      <header className="flex items-center justify-between gap-2 border-b border-[var(--border)] px-4 py-2.5">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          {title}
        </h2>
        {aside}
      </header>
      <div className="p-4">{children}</div>
    </section>
  );
}

/**
 * Broker Workspace — configuration only.
 * Connection · Diagnostics · Settings. No metrics, charts, or ops dashboards.
 */
export function BrokerConfigWorkspace() {
  const qc = useQueryClient();
  const session = useTradingSession();

  const healthQ = useQuery({
    queryKey: ["weltrade-health"],
    queryFn: weltradeApi.health,
    staleTime: 10_000,
    refetchInterval: 12_000,
    retry: 2,
  });
  const mt5Q = useQuery({
    queryKey: ["mt5-status"],
    queryFn: mt5Api.status,
    staleTime: 10_000,
    refetchInterval: 12_000,
    retry: false,
  });
  const profileQ = useQuery({
    queryKey: ["weltrade-profile"],
    queryFn: weltradeApi.profile,
    staleTime: 60_000,
    retry: false,
  });
  const tickQ = useQuery({
    queryKey: ["mt5-tick", TRADING_SYMBOL, "broker-diag"],
    queryFn: () => mt5Api.tick(TRADING_SYMBOL),
    enabled: session.connected,
    staleTime: 5_000,
    refetchInterval: session.connected ? 8_000 : false,
    retry: false,
  });

  const health = asRecord(healthQ.data);
  const mt5 = asRecord(mt5Q.data);
  const profile = asRecord(profileQ.data);
  const tick = asRecord(tickQ.data);

  const connected = session.connected || Boolean(health.mt5_connected || health.mt5_attached || mt5.connected);
  const gatewayOnline =
    session.gatewayOnline || Boolean(health.gateway_online || health.gateway_reachable);
  const loginOk =
    connected &&
    (str(session.loginStatus).toLowerCase().includes("log") ||
      Boolean(mt5.login) ||
      Boolean(session.login && session.login !== "—"));

  const [accountType, setAccountType] = useState<AccountType>("live");
  const [provider] = useState("MetaTrader 5");
  const [broker, setBroker] = useState("Weltrade");
  const [server, setServer] = useState("Weltrade-Real");
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [terminalPath, setTerminalPath] = useState("");
  const [progress, setProgress] = useState<string | null>(null);

  const serverOptions = useMemo(() => {
    const servers = asRecord(asRecord(profile).servers);
    const list = Array.isArray(servers[accountType])
      ? (servers[accountType] as string[])
      : [];
    if (list.length) return list;
    return accountType === "demo" ? ["Weltrade-Demo"] : ["Weltrade-Real"];
  }, [profile, accountType]);

  useEffect(() => {
    if (!serverOptions.includes(server)) {
      setServer(serverOptions[0] ?? "Weltrade-Real");
    }
  }, [serverOptions, server]);

  useEffect(() => {
    const liveLogin = str(mt5.login || session.login);
    if (liveLogin && liveLogin !== "—" && !login) setLogin(liveLogin);
    const liveServer = str(mt5.server || session.server);
    if (liveServer && liveServer !== "—") setServer(liveServer);
  }, [mt5.login, mt5.server, session.login, session.server, login]);

  const refresh = async () => {
    await session.invalidateAll();
    await Promise.all([healthQ.refetch(), mt5Q.refetch()]);
  };

  const connectMut = useMutation({
    mutationFn: weltradeApi.connect,
    onMutate: () => setProgress("Connecting…"),
    onSuccess: async (data) => {
      setPassword("");
      const body = asRecord(asRecord(data).dashboard);
      if (Object.keys(body).length > 0) {
        qc.setQueryData(["weltrade-dashboard"], body);
      }
      toast.success("Broker connected");
      await refresh();
      setProgress(null);
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
      await refresh();
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Disconnect failed"),
  });

  const testMut = useMutation({
    mutationFn: async () => {
      const h = await weltradeApi.health();
      const m = await mt5Api.status();
      if (asRecord(m).connected) {
        await mt5Api.tick(TRADING_SYMBOL);
      }
      return { health: h, mt5: m };
    },
    onMutate: () => setProgress("Testing connection…"),
    onSuccess: async () => {
      toast.success("Connection test completed");
      await refresh();
      setProgress(null);
    },
    onError: (e) => {
      setProgress(null);
      toast.error(e instanceof ApiError ? e.message : "Test failed");
    },
  });

  const saveMut = useMutation({
    mutationFn: async () => {
      const loginNum = Number(login);
      if (!Number.isFinite(loginNum) || loginNum <= 0) {
        throw new Error("Enter a valid login");
      }
      return weltradeApi.connect({
        login: loginNum,
        password: password || undefined,
        server,
        account_type: accountType,
        prefer_attach: true,
        path: terminalPath || undefined,
        remember_on_gateway: true,
      });
    },
    onMutate: () => setProgress("Saving…"),
    onSuccess: async () => {
      setPassword("");
      toast.success("Broker settings saved to gateway session");
      await refresh();
      setProgress(null);
    },
    onError: (e) => {
      setProgress(null);
      toast.error(e instanceof Error ? e.message : "Save failed");
    },
  });

  const busy =
    connectMut.isPending ||
    disconnectMut.isPending ||
    testMut.isPending ||
    saveMut.isPending;

  const onConnect = () => {
    const loginNum = Number(login);
    if (!Number.isFinite(loginNum) || loginNum <= 0) {
      toast.error("Enter a valid login");
      return;
    }
    connectMut.mutate({
      login: loginNum,
      password: password || undefined,
      server,
      account_type: accountType,
      prefer_attach: true,
      path: terminalPath || undefined,
      remember_on_gateway: true,
    });
  };

  const latency =
    session.latencyMs !== "—"
      ? `${session.latencyMs} ms`
      : mt5.latency_ms != null
        ? `${str(mt5.latency_ms)} ms`
        : "—";
  const heartbeat = (session.heartbeatAt || str(mt5.last_heartbeat_at, "—"))
    .replace("T", " ")
    .slice(0, 19);

  const tradingAllowed =
    connected &&
    (health.execution_enabled === true ||
      str(asRecord(health.account).trade_mode).toLowerCase() !== "disabled");
  const marketOpen = connected && (tick.bid != null || tick.ask != null);
  const symbolAvailable = connected && (tickQ.isSuccess || tick.bid != null);
  const pingHealthy =
    connected &&
    (Number(session.latencyMs) < 5000 ||
      (typeof mt5.latency_ms === "number" && mt5.latency_ms < 5000));

  // Terminal-side flags — report only when gateway/health exposes them
  const autoTrading =
    health.mt5_autotrading_enabled == null
      ? null
      : Boolean(health.mt5_autotrading_enabled);
  const dllEnabled =
    health.dll_allowed == null && health.dll_enabled == null
      ? null
      : Boolean(health.dll_allowed ?? health.dll_enabled);

  if (healthQ.isLoading && mt5Q.isLoading && !session.login) {
    return <DeskSkeleton rows={6} />;
  }

  return (
    <div className="mx-auto max-w-3xl space-y-3">
      <header className="border border-[var(--border)] bg-[var(--surface)] px-4 py-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-[10px] uppercase tracking-[0.16em] text-[var(--fg-subtle)]">
              Operations · Broker
            </p>
            <h1 className="mt-1 font-display text-xl tracking-tight text-[var(--fg)]">
              Broker Workspace
            </h1>
            <p className="mt-1 text-sm text-[var(--fg-muted)]">
              Connection, diagnostics, and settings only. Observability lives in Monitoring.
            </p>
          </div>
          <Badge tone={connected ? "success" : gatewayOnline ? "warning" : "neutral"}>
            {connected ? "Connected" : gatewayOnline ? "Gateway ready" : "Offline"}
          </Badge>
        </div>
      </header>

      <Section
        title="A · Connection"
        aside={
          <Button
            size="sm"
            variant="ghost"
            disabled={session.refreshing}
            onClick={() => void refresh()}
          >
            <RefreshCw
              className={cn("h-3.5 w-3.5", session.refreshing && "animate-spin")}
            />
            Refresh
          </Button>
        }
      >
        <div className="grid gap-2 sm:grid-cols-2">
          <Field label="Broker Status" value={connected ? "Connected" : "Disconnected"} />
          <Field label="Broker Name" value={str(asRecord(health.account).company || broker, "Weltrade")} />
          <Field label="Server" value={str(mt5.server || session.server, "—")} />
          <Field label="Login" value={str(mt5.login || session.login, "—")} />
          <Field label="Latency" value={latency} />
          <Field label="Heartbeat" value={heartbeat} />
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
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
          <Button variant="outline" disabled={busy} onClick={() => testMut.mutate()}>
            <RefreshCw className="h-4 w-4" />
            Test Connection
          </Button>
        </div>
        {progress ? (
          <p className="mt-3 flex items-center gap-2 text-sm text-[var(--accent)]">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            {progress}
          </p>
        ) : null}
      </Section>

      <Section title="B · Diagnostics">
        <div className="grid gap-2 sm:grid-cols-2">
          <Diag ok={connected} label="MT5 Running" />
          <Diag ok={gatewayOnline} label="Gateway Connected" />
          <Diag ok={loginOk} label="Login OK" />
          <Diag ok={tradingAllowed} label="Trading Allowed" />
          <Diag ok={autoTrading} label="AutoTrading Enabled" />
          <Diag ok={dllEnabled} label="DLL Enabled" />
          <Diag ok={marketOpen} label="Market Open" />
          <Diag ok={symbolAvailable} label="Symbol Available (XAUUSD)" />
          <Diag ok={pingHealthy} label="Ping Healthy" />
        </div>
        <p className="mt-3 text-[11px] text-[var(--fg-subtle)]">
          AutoTrading / DLL reflect terminal-side flags when the gateway reports them; otherwise
          shown as unknown (—) — never invented.
        </p>
      </Section>

      <Section title="C · Broker Settings">
        <div className="mb-4 grid grid-cols-2 gap-2">
          {(["demo", "live"] as const).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setAccountType(t)}
              className={cn(
                "border px-3 py-2 text-sm capitalize transition",
                accountType === t
                  ? "border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--fg)]"
                  : "border-[var(--border)] text-[var(--fg-muted)] hover:border-[var(--border-strong)]",
              )}
            >
              {t}
            </button>
          ))}
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="bw-provider">Provider</Label>
            <Input id="bw-provider" value={provider} readOnly disabled />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="bw-broker">Broker</Label>
            <Input
              id="bw-broker"
              value={broker}
              onChange={(e) => setBroker(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="bw-server">Server</Label>
            <select
              id="bw-server"
              className="flex h-10 w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 text-sm"
              value={server}
              onChange={(e) => setServer(e.target.value)}
            >
              {serverOptions.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
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
          <div className="space-y-1.5 sm:col-span-2">
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
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="bw-path">Terminal Path</Label>
            <Input
              id="bw-path"
              value={terminalPath}
              onChange={(e) => setTerminalPath(e.target.value)}
              placeholder="Optional — leave blank to auto-attach"
            />
          </div>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <Button disabled={busy} onClick={() => saveMut.mutate()}>
            {saveMut.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : null}
            Save
          </Button>
          <Button variant="outline" disabled={busy} onClick={() => testMut.mutate()}>
            Test Connection
          </Button>
        </div>
        <p className="mt-3 text-[11px] text-[var(--fg-subtle)]">
          Password is sent to the local gateway only — never stored in the browser database.
        </p>
      </Section>
    </div>
  );
}
