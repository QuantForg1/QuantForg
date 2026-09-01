"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Cable,
  Loader2,
  RefreshCw,
  Unplug,
} from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ConnectionStatus } from "@/components/trading/connection-status";
import { mt5Api, marketUniverseApi, tradingSessionApi, weltradeApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asRecord, str } from "@/lib/desk";
import {
  MARKET_UNIVERSE_QUERY_KEY,
  SIGNAL_CENTER_QUERY_KEY,
  latencyLabel,
  researchDeskLiveTradingStatus,
  resolveConnectionPresentation,
  traderFacingErrorMessage,
} from "@/lib/trading/trader-ux";
import { useTradingSession } from "@/providers/trading-session-provider";
import { useAuth } from "@/providers/auth-provider";
import { canAccessIteOps } from "@/lib/auth/ite-ops-access";
import { cn } from "@/lib/utils";

type AccountType = "demo" | "live";

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
  const { user } = useAuth();
  const isOperator = canAccessIteOps(user);

  const tradingSessionQ = useQuery({
    queryKey: ["trading-session"],
    queryFn: tradingSessionApi.session,
    staleTime: 10_000,
    refetchInterval: 15_000,
    retry: false,
  });

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

  const health = asRecord(healthQ.data);
  const mt5 = asRecord(mt5Q.data);
  const profile = asRecord(profileQ.data);

  // Owned trading session is the only "Connected" truth.
  // Gateway / MT5 process health must never invent a user-owned connection.
  const tradingSnapEarly = asRecord(tradingSessionQ.data);
  const connectionEarly = resolveConnectionPresentation(tradingSnapEarly, {
    connecting: false,
  });
  const connected =
    connectionEarly.connected && connectionEarly.ownership === "owned";
  const gatewayOnline = Boolean(
    health.gateway_online || health.gateway_reachable,
  );
  const gatewayMt5Attached = Boolean(
    health.mt5_connected || health.mt5_attached || mt5.connected,
  );

  const [accountType, setAccountType] = useState<AccountType>("live");
  const [server, setServer] = useState("Weltrade-Real");
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [passwordFieldKey, setPasswordFieldKey] = useState(0);
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
    if (session.connected) setPassword("");
  }, [mt5.login, mt5.server, session.login, session.server, session.connected, login]);

  const refresh = async () => {
    await session.invalidateAll();
    await Promise.all([healthQ.refetch(), mt5Q.refetch()]);
  };

  const refreshOwnedCatalogue = async () => {
    try {
      await marketUniverseApi.refresh();
    } catch {
      /* catalogue remains unverified — never invent LIVE_BROKER */
    }
    await qc.invalidateQueries({ queryKey: MARKET_UNIVERSE_QUERY_KEY });
    await qc.invalidateQueries({ queryKey: SIGNAL_CENTER_QUERY_KEY });
  };

  const clearPasswordField = () => {
    setPassword("");
    setPasswordFieldKey((key) => key + 1);
  };
  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      if (connected) return;
      try {
        const meta = await weltradeApi.runtimeProfile();
        const profileRow = asRecord(meta.profile);
        if (!profileRow.login) return;
        // Prefill configured credentials only — never claim Connected from profile.
        if (!cancelled && !login) setLogin(String(profileRow.login));
        if (!cancelled && profileRow.server) setServer(String(profileRow.server));
        if (!cancelled && profileRow.terminal_path) {
          setTerminalPath(String(profileRow.terminal_path));
        }
        // Secure restore may re-attach an owned session when the gateway supports it.
        await weltradeApi.restoreProfile();
        if (!cancelled) await refresh();
      } catch {
        /* no profile or restore unavailable — user can connect manually */
      }
    };
    void run();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- one-shot restore on mount
  }, []);

  const connectMut = useMutation({
    mutationFn: weltradeApi.connect,
    onMutate: () => {
      clearPasswordField();
      setProgress("CONNECTING");
    },
    onSuccess: async (data) => {
      clearPasswordField();
      const body = asRecord(asRecord(data).dashboard);
      if (Object.keys(body).length > 0) {
        qc.setQueryData(["weltrade-dashboard"], body);
      }
      toast.success("CONNECTED");
      await qc.invalidateQueries({ queryKey: ["trading-session"] });
      await refresh();
      await refreshOwnedCatalogue();
      setProgress(null);
    },
    onError: (e) => {
      clearPasswordField();
      setProgress(null);
      toast.error(
        e instanceof ApiError
          ? traderFacingErrorMessage(e)
          : "CONNECTION_FAILED",
      );
    },
  });

  const disconnectMut = useMutation({
    mutationFn: weltradeApi.disconnect,
    onSuccess: async () => {
      toast.success("Disconnected");
      await refresh();
      await qc.invalidateQueries({ queryKey: MARKET_UNIVERSE_QUERY_KEY });
    },
    onError: (e) =>
      toast.error(
        e instanceof ApiError ? traderFacingErrorMessage(e) : "Disconnect failed",
      ),
  });

  const saveMut = useMutation({
    mutationFn: async () => {
      const loginNum = Number(login);
      if (!Number.isFinite(loginNum) || loginNum <= 0) {
        throw new Error("Enter a valid login");
      }
      const submittedPassword = password;
      clearPasswordField();
      return weltradeApi.connect({
        login: loginNum,
        password: submittedPassword || undefined,
        server,
        account_type: accountType,
        prefer_attach: true,
        path: terminalPath || undefined,
        remember_on_gateway: true,
      });
    },
    onMutate: () => {
      setProgress("CONNECTING");
    },
    onSuccess: async () => {
      clearPasswordField();
      toast.success("CONNECTED");
      await refresh();
      await refreshOwnedCatalogue();
      setProgress(null);
    },
    onError: (e) => {
      clearPasswordField();
      setProgress(null);
      toast.error(
        e instanceof ApiError
          ? traderFacingErrorMessage(e)
          : e instanceof Error
            ? traderFacingErrorMessage({ message: e.message })
            : "CONNECTION_FAILED",
      );
    },
  });

  const busy =
    connectMut.isPending ||
    disconnectMut.isPending ||
    saveMut.isPending;

  const onConnect = () => {
    if (connected) {
      toast.message("Broker already connected");
      return;
    }
    const loginNum = Number(login);
    if ((!Number.isFinite(loginNum) || loginNum <= 0) && !password) {
      // Configured profile may exist server-side — prefer reconnect.
      void (async () => {
        setProgress("Reconnecting…");
        try {
          await weltradeApi.reconnect();
          toast.success("Broker reconnected");
          await refresh();
        } catch (e) {
          try {
            await weltradeApi.restoreProfile();
            toast.success("Broker restored from secure profile");
            await refresh();
          } catch {
            toast.error(
              e instanceof ApiError
                ? traderFacingErrorMessage(e)
                : "CONNECTION_FAILED",
            );
          }
        } finally {
          setProgress(null);
        }
      })();
      return;
    }
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

  const tradingSnap = tradingSnapEarly;
  const connectionView = resolveConnectionPresentation(tradingSnap, {
    connecting: Boolean(progress) || connectMut.isPending || saveMut.isPending,
  });
  const uxState = str(
    tradingSnap.ux_state,
    connected ? "CONNECTED" : "NO_BROKER",
  );
  const showConnectForm = !connected || uxState === "SESSION_MISMATCH";

  const liveTradingHint = researchDeskLiveTradingStatus(
    connectionView,
    tradingSnap.trading,
    {
      liveTradingState: tradingSnap.live_trading_state,
      ordersMaySubmit: tradingSnap.orders_may_submit,
      liveAuthorization: tradingSnap.live_authorization,
    },
  );
  const isLiveAccount = accountType === "live";
  const latency =
    session.latencyMs && session.latencyMs !== "—"
      ? latencyLabel(Number(session.latencyMs))
      : "Not available";

  const showPasswordField =
    showConnectForm && !connectMut.isPending && !saveMut.isPending;

  const onReconnect = () => {
    void (async () => {
      setProgress("Reconnecting…");
      try {
        await weltradeApi.reconnect();
        toast.success("Broker reconnected");
        await refresh();
      } catch (e) {
        toast.error(
          e instanceof ApiError ? traderFacingErrorMessage(e) : "CONNECTION_FAILED",
        );
      } finally {
        setProgress(null);
      }
    })();
  };

  const onVerify = () => {
    if (showConnectForm) {
      saveMut.mutate();
      return;
    }
    onReconnect();
  };

  return (
    <div className="mx-auto w-full min-w-0 max-w-2xl space-y-4 px-1 sm:px-0">
      <PageHeader
        title="Broker"
        description="Connect your MT5 account to access your broker account, portfolio data and, when authorized, live execution."
      />

      <p className="text-sm leading-relaxed text-[var(--fg-muted)]">
        Connecting your broker gives QuantForg access to account information. Live trading
        requires the existing authorization and risk controls.
      </p>

      <ConnectionStatus
        session={tradingSnap}
        connecting={
          (Boolean(progress) && !connected) || connectMut.isPending || saveMut.isPending
        }
      />

      {connected && uxState !== "SESSION_MISMATCH" ? (
        <Section
          title="CONNECTED"
          aside={
            isLiveAccount ? (
              <span className="text-[11px] font-semibold uppercase tracking-wide text-[var(--warning)]">
                Live account
              </span>
            ) : (
              <span className="text-[11px] font-semibold uppercase tracking-wide text-[var(--fg-subtle)]">
                Demo
              </span>
            )
          }
        >
          <dl className="grid gap-3 sm:grid-cols-2">
            <div>
              <dt className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                Broker
              </dt>
              <dd className="text-sm text-[var(--fg)]">Weltrade / MT5</dd>
            </div>
            <div>
              <dt className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                Server
              </dt>
              <dd className="text-sm text-[var(--fg)]">{connectionView.server || "N/A"}</dd>
            </div>
            <div>
              <dt className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                Account
              </dt>
              <dd className="text-sm text-[var(--fg)]">{connectionView.maskedLogin}</dd>
            </div>
            <div>
              <dt className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                Balance
              </dt>
              <dd className="text-sm text-[var(--fg)]">
                {session.balance && session.balance !== "—" ? session.balance : "N/A"}
              </dd>
            </div>
            <div>
              <dt className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                Equity
              </dt>
              <dd className="text-sm text-[var(--fg)]">
                {session.equity && session.equity !== "—" ? session.equity : "N/A"}
              </dd>
            </div>
            <div>
              <dt className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                Free margin
              </dt>
              <dd className="text-sm text-[var(--fg)]">
                {session.freeMargin && session.freeMargin !== "—"
                  ? session.freeMargin
                  : "N/A"}
              </dd>
            </div>
            <div>
              <dt className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                Connection latency
              </dt>
              <dd className="text-sm text-[var(--fg)]">
                {latency === "—" ? "N/A" : latency}
              </dd>
            </div>
            <div>
              <dt className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                Last verified
              </dt>
              <dd className="text-sm text-[var(--fg)]">
                {connectionView.lastVerified || "N/A"}
              </dd>
            </div>
            <div>
              <dt className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                MT5 status
              </dt>
              <dd className="text-sm text-[var(--fg)]">
                {gatewayMt5Attached
                  ? connected
                    ? "Attached (owned)"
                    : "Attached (not owned by you)"
                  : "Not attached"}
              </dd>
            </div>
            <div>
              <dt className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                Gateway status
              </dt>
              <dd className="text-sm text-[var(--fg)]">
                {gatewayOnline
                  ? "Online"
                  : healthQ.isError
                    ? "Unavailable"
                    : "Offline"}
              </dd>
            </div>
            <div>
              <dt className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                Ownership
              </dt>
              <dd className="text-sm text-[var(--fg)]">
                {connectionView.ownership === "owned" ? "Owned by you" : "None"}
              </dd>
            </div>
            <div>
              <dt className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                Live trading
              </dt>
              <dd className="text-sm text-[var(--fg)]">{liveTradingHint.label}</dd>
            </div>
          </dl>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button variant="secondary" disabled={busy} onClick={onReconnect}>
              <RefreshCw className="h-4 w-4" />
              Reconnect
            </Button>
            <Button variant="secondary" disabled={busy} onClick={onVerify}>
              Verify connection
            </Button>
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() => disconnectMut.mutate()}
            >
              <Unplug className="h-4 w-4" />
              Disconnect
            </Button>
          </div>
        </Section>
      ) : (
        <Section title="Connection">
          <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <dt className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                Broker
              </dt>
              <dd className="text-sm text-[var(--fg)]">NOT CONNECTED</dd>
            </div>
            <div>
              <dt className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                Gateway
              </dt>
              <dd className="text-sm text-[var(--fg)]">
                {gatewayOnline
                  ? "Online"
                  : healthQ.isError
                    ? "Unavailable"
                    : "Offline"}
              </dd>
            </div>
            <div>
              <dt className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                MT5
              </dt>
              <dd className="text-sm text-[var(--fg)]">
                {gatewayMt5Attached ? "Attached (not owned by you)" : "Not attached"}
              </dd>
            </div>
            <div>
              <dt className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                Live trading
              </dt>
              <dd className="text-sm text-[var(--fg)]">{liveTradingHint.label}</dd>
            </div>
          </dl>
          {!connected && gatewayMt5Attached ? (
            <p className="mt-3 text-xs text-[var(--warning)]">
              A gateway session may exist, but it is not your owned broker connection.
              Use Connect MT5 to claim ownership.
            </p>
          ) : null}
        </Section>
      )}

      <Section
        title="Connect MT5"
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
        {uxState === "SESSION_MISMATCH" ? (
          <p className="mb-3 text-sm text-[var(--warning)]">
            ACCOUNT SESSION MISMATCH. Reconnect your own account.
          </p>
        ) : null}
        {showConnectForm ? (
          <>
            <div className="mb-4 grid grid-cols-2 gap-2">
              {(["demo", "live"] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setAccountType(t)}
                  className={cn(
                    "border px-3 py-2 text-sm capitalize transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]",
                    accountType === t
                      ? "border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--fg)]"
                      : "border-[var(--border)] text-[var(--fg-muted)] hover:border-[var(--border-strong)]",
                  )}
                >
                  {t === "live" ? "Live" : "Demo"}
                </button>
              ))}
            </div>
            <div className="grid gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="bw-server">Broker / Server</Label>
                <select
                  id="bw-server"
                  className="flex h-10 w-full min-w-0 rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 text-sm"
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
                <Label htmlFor="bw-login">MT5 Login</Label>
                <Input
                  id="bw-login"
                  inputMode="numeric"
                  autoComplete="username"
                  value={login}
                  onChange={(e) => setLogin(e.target.value)}
                  placeholder="Account number"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="bw-password">Password</Label>
                {showPasswordField ? (
                  <Input
                    key={passwordFieldKey}
                    id="bw-password"
                    type="password"
                    autoComplete="off"
                    name="broker-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Required to verify the connection"
                  />
                ) : (
                  <p className="text-sm text-[var(--fg-subtle)]">
                    Password submitted. It is never displayed again.
                  </p>
                )}
              </div>
              {isOperator ? (
                <div className="space-y-1.5">
                  <Label htmlFor="bw-path">Terminal Path</Label>
                  <Input
                    id="bw-path"
                    value={terminalPath}
                    onChange={(e) => setTerminalPath(e.target.value)}
                    placeholder="Optional — leave blank to auto-attach"
                  />
                </div>
              ) : null}
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <Button disabled={busy} onClick={onConnect}>
                {connectMut.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Cable className="h-4 w-4" />
                )}
                Connect MT5
              </Button>
              <Button variant="secondary" disabled={busy} onClick={onVerify}>
                Verify connection
              </Button>
            </div>
            {progress ? (
              <p className="mt-3 flex items-center gap-2 text-sm text-[var(--accent)]">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                {progress}
              </p>
            ) : null}
            <p className="mt-3 text-[11px] text-[var(--fg-subtle)]">
              Password is used only to submit this form. It is never stored in the browser,
              localStorage, or API responses.
            </p>
          </>
        ) : (
          <p className="text-sm text-[var(--fg-muted)]">
            Connected. Use Reconnect, Verify, or Disconnect above.
          </p>
        )}
      </Section>

      <Section title="Security">
        <ul className="space-y-2 text-sm text-[var(--fg-muted)]">
          <li>Credentials are protected through the existing secure session mechanism.</li>
          <li>Password is never displayed after submission.</li>
          <li>Account number is masked.</li>
          <li>The connection can be revoked at any time with Disconnect.</li>
          <li>QuantForg does not bypass broker, ownership, or risk controls.</li>
        </ul>
      </Section>
    </div>
  );
}
