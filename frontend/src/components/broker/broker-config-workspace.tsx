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
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DeskSkeleton } from "@/components/desk/primitives";
import { ConnectionStatus } from "@/components/trading/connection-status";
import { mt5Api, tradingSessionApi, weltradeApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asRecord, str } from "@/lib/desk";
import { traderFacingErrorMessage } from "@/lib/trading/trader-ux";
import { useTradingSession } from "@/providers/trading-session-provider";
import { useAuth } from "@/providers/auth-provider";
import { canAccessIteOps } from "@/lib/auth/ite-ops-access";
import { cn } from "@/lib/utils";

type AccountType = "demo" | "live";

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

  const connected = session.connected || Boolean(health.mt5_connected || health.mt5_attached || mt5.connected);

  const [accountType, setAccountType] = useState<AccountType>("live");
  const [provider] = useState("MetaTrader 5");
  const [broker, setBroker] = useState("Weltrade");
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
        if (!cancelled && !login) setLogin(String(profileRow.login));
        if (!cancelled && profileRow.server) setServer(String(profileRow.server));
        if (!cancelled && profileRow.terminal_path) {
          setTerminalPath(String(profileRow.terminal_path));
        }
        if (!cancelled && profileRow.broker) setBroker(String(profileRow.broker));
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
      setProgress("Connecting to your broker...");
    },
    onSuccess: async (data) => {
      clearPasswordField();
      const body = asRecord(asRecord(data).dashboard);
      if (Object.keys(body).length > 0) {
        qc.setQueryData(["weltrade-dashboard"], body);
      }
      toast.success("Broker connected");
      await qc.invalidateQueries({ queryKey: ["trading-session"] });
      await refresh();
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
      setProgress("Saving…");
    },
    onSuccess: async () => {
      clearPasswordField();
      toast.success("Broker configured — session validated and connected");
      await refresh();
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

  const heartbeat = (session.heartbeatAt || str(mt5.last_heartbeat_at, "—"))
    .replace("T", " ")
    .slice(0, 19);

  const tradingSnap = asRecord(tradingSessionQ.data);
  const uxState = str(tradingSnap.ux_state, connected ? "CONNECTED" : "NO_BROKER");
  const maskedAccount = str(tradingSnap.account, "—");
  const maskedServer = str(tradingSnap.server, str(mt5.server || session.server, "—"));
  const lastVerified = str(tradingSnap.last_verified, heartbeat);
  const healthLabel =
    uxState === "SESSION_MISMATCH"
      ? "ACCOUNT_SESSION_MISMATCH"
      : connected
        ? "CONNECTED"
        : connectMut.isPending || saveMut.isPending
          ? "CONNECTING"
          : "BROKER NOT CONNECTED";
  const showConnectForm = !connected || uxState === "SESSION_MISMATCH";

  const showPasswordField =
    showConnectForm && !connectMut.isPending && !saveMut.isPending;

  if (healthQ.isLoading && mt5Q.isLoading && !session.login) {
    return <DeskSkeleton rows={6} />;
  }

  return (
    <div className="mx-auto w-full min-w-0 max-w-3xl space-y-4 px-1 sm:px-0">
      <PageHeader
        title={connected ? "Broker" : "Connect Broker"}
        description={
          connected
            ? "Your owned connection. Password is never shown after verification."
            : "Login, server, password, then Verify. Password is sent securely and never kept in the browser."
        }
        actions={
          <Badge
            tone={
              connected && uxState !== "SESSION_MISMATCH"
                ? "success"
                : connectMut.isPending
                  ? "warning"
                  : "neutral"
            }
          >
            {healthLabel}
          </Badge>
        }
      />

      <ConnectionStatus
        session={tradingSnap}
        connecting={Boolean(progress) && !connected}
      />

      <Section
        title="Your account"
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
          <Field label="Connection status" value={healthLabel} />
          <Field label="Masked login" value={maskedAccount} />
          <Field label="Server" value={maskedServer} />
          <Field label="Last verified" value={lastVerified} />
          <Field
            label="Ownership"
            value={str(tradingSnap.ownership, connected ? "owned" : "none")}
          />
        </div>
        {uxState === "SESSION_MISMATCH" ? (
          <p className="mt-3 text-sm text-[var(--warning)]">
            ACCOUNT_SESSION_MISMATCH. Reconnect your own account. Concurrent independent live logins are not supported.
          </p>
        ) : null}
        <div className="mt-4 flex flex-wrap gap-2">
          <Button disabled={busy} onClick={onConnect}>
            {connectMut.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Cable className="h-4 w-4" />
            )}
            {connected ? "Reconnect" : "Connect & Verify"}
          </Button>
          <Button
            variant="secondary"
            disabled={busy || !connected}
            onClick={() => disconnectMut.mutate()}
          >
            <Unplug className="h-4 w-4" />
            Disconnect
          </Button>
        </div>
        {progress ? (
          <p className="mt-3 flex items-center gap-2 text-sm text-[var(--accent)]">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            {progress}
          </p>
        ) : null}
      </Section>

      {showConnectForm ? (
      <Section title="Connect Broker">
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
                Password submitted. It is not kept on this page.
              </p>
            )}
          </div>
          {isOperator ? (
          <div className="space-y-1.5 sm:col-span-2">
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
          <Button disabled={busy} onClick={() => saveMut.mutate()}>
            {saveMut.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : null}
            Verify Connection
          </Button>
        </div>
        <p className="mt-3 text-[11px] text-[var(--fg-subtle)]">
          Password is used only to submit this form. It is never stored in the browser, localStorage, or API responses.
        </p>
      </Section>
      ) : null}
    </div>
  );
}
