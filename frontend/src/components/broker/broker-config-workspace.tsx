"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Building2,
  Check,
  CheckCircle2,
  ChevronDown,
  Coins,
  Eye,
  EyeOff,
  Layers,
  Link2,
  Link2Off,
  Loader2,
  Lock,
  Pencil,
  RefreshCw,
  Search,
  Server,
  ShieldCheck,
  Unplug,
  UserRound,
  Wallet,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { BrokerLogo, Mt5BrandMark } from "@/components/broker/broker-logo";
import {
  brokerConnectivityApi,
  mt5Api,
  marketUniverseApi,
  tradingSessionApi,
  weltradeApi,
} from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, str } from "@/lib/desk";
import {
  MARKET_UNIVERSE_QUERY_KEY,
  SIGNAL_CENTER_QUERY_KEY,
  ownershipBlockMessage,
  resolveConnectionPresentation,
  researchDeskLiveTradingStatus,
  traderFacingErrorMessage,
} from "@/lib/trading/trader-ux";
import { useTradingSession } from "@/providers/trading-session-provider";
import { useAuth } from "@/providers/auth-provider";
import { canAccessIteOps } from "@/lib/auth/ite-ops-access";
import { cn } from "@/lib/utils";
import {
  MT5_BROKER_OPTIONS,
  type Mt5BrokerOption,
  type Mt5BrokerSlug,
  type Mt5ServerRow,
  brokerBySlug,
  mapRegistryBrokers,
  matchBrokerByServer,
  serversForBroker,
} from "@/lib/broker/mt5-broker-catalog";

type AccountType = "demo" | "live";

function inferAccountType(serverName: string): AccountType {
  const s = serverName.toLowerCase();
  if (s.includes("demo") || s.includes("trial")) return "demo";
  return "live";
}

function FieldShell({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex h-12 w-full items-center gap-2.5 rounded-xl border border-[color-mix(in_srgb,var(--accent)_22%,var(--border))] bg-[color-mix(in_srgb,var(--bg)_55%,transparent)] px-3 text-sm text-[var(--fg)] shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]",
        className,
      )}
    >
      {children}
    </div>
  );
}

function SecurityFooter() {
  return (
    <div className="mt-6 flex items-start gap-3 rounded-xl border border-[var(--border)] bg-[color-mix(in_srgb,var(--surface)_55%,transparent)] px-4 py-3">
      <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-[var(--accent)]" aria-hidden />
      <p className="text-[12px] leading-relaxed text-[var(--fg-muted)]">
        <span className="font-semibold text-[var(--fg)]">Secure &amp; Private Connection</span>
        {" — "}
        Trading passwords are encrypted at rest with AES-256-GCM, never returned in browser
        responses, and never written to application logs.
      </p>
    </div>
  );
}

function BrokerSelect({
  value,
  options,
  onChange,
  disabled,
}: {
  value: Mt5BrokerSlug | null;
  options: readonly Mt5BrokerOption[];
  onChange: (broker: Mt5BrokerOption) => void;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const rootRef = useRef<HTMLDivElement>(null);
  const selected = options.find((b) => b.slug === value) ?? (value ? brokerBySlug(value) : undefined);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return options;
    return options.filter((b) => b.name.toLowerCase().includes(q));
  }, [query, options]);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="w-full text-left"
      >
        <FieldShell className={cn(open && "border-[var(--accent)] ring-1 ring-[var(--ring)]")}>
          {selected ? (
            <BrokerLogo src={selected.logoSrc} name={selected.name} size={22} rounded="md" />
          ) : (
            <Building2 className="h-4 w-4 shrink-0 text-[var(--fg-subtle)]" aria-hidden />
          )}
          <span
            className={cn(
              "min-w-0 flex-1 truncate",
              selected ? "text-[var(--fg)]" : "text-[var(--fg-subtle)]",
            )}
          >
            {selected ? selected.name : "Select a broker"}
          </span>
          <ChevronDown
            className={cn(
              "h-4 w-4 shrink-0 text-[var(--fg-subtle)] transition",
              open && "rotate-180",
            )}
            aria-hidden
          />
        </FieldShell>
      </button>

      {open ? (
        <div
          role="listbox"
          className="absolute z-40 mt-2 w-full overflow-hidden rounded-xl border border-[color-mix(in_srgb,var(--accent)_28%,var(--border))] bg-[color-mix(in_srgb,#071528_92%,transparent)] shadow-[var(--shadow-elevated)] backdrop-blur-xl"
        >
          <div className="border-b border-[var(--border)] p-2">
            <label className="flex h-9 items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg)]/40 px-2.5">
              <Search className="h-3.5 w-3.5 text-[var(--fg-subtle)]" aria-hidden />
              <input
                autoFocus
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search broker..."
                className="w-full bg-transparent text-sm outline-none placeholder:text-[var(--fg-subtle)]"
              />
            </label>
          </div>
          <ul className="max-h-64 overflow-y-auto py-1">
            {filtered.map((broker) => {
              const active = broker.slug === value;
              return (
                <li key={broker.slug}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={active}
                    className={cn(
                      "flex w-full items-center gap-3 px-3 py-2.5 text-left text-sm transition hover:bg-[var(--accent-soft)]",
                      active && "bg-[var(--accent-soft)]",
                    )}
                    onClick={() => {
                      onChange(broker);
                      setOpen(false);
                      setQuery("");
                    }}
                  >
                    <BrokerLogo src={broker.logoSrc} name={broker.name} size={28} rounded="md" />
                    <span className="min-w-0 flex-1 truncate font-medium">{broker.name}</span>
                    <span className="rounded-md border border-[color-mix(in_srgb,var(--accent)_40%,transparent)] bg-[var(--accent-soft)] px-1.5 py-0.5 text-[10px] font-semibold tracking-wide text-[var(--accent)]">
                      MT5
                    </span>
                    <span
                      className={cn(
                        "rounded-md px-1.5 py-0.5 text-[10px] font-semibold",
                        broker.connectable
                          ? "bg-[color-mix(in_srgb,var(--success)_16%,transparent)] text-[var(--success)]"
                          : "bg-[var(--surface-2)] text-[var(--fg-subtle)]",
                      )}
                    >
                      {broker.connectable ? "Verified" : "Pending"}
                    </span>
                    {active ? (
                      <Check className="h-4 w-4 shrink-0 text-[var(--accent)]" aria-hidden />
                    ) : (
                      <span className="w-4" />
                    )}
                  </button>
                </li>
              );
            })}
            {!filtered.length ? (
              <li className="px-3 py-4 text-center text-sm text-[var(--fg-muted)]">
                No brokers match that search.
              </li>
            ) : null}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

/**
 * Broker Workspace — Connect MT5 Account UI.
 * Connection · ownership · reconnect. Balance/status from live session only.
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
  const exposureQ = useQuery({
    queryKey: ["weltrade-exposure"],
    queryFn: weltradeApi.exposure,
    staleTime: 5_000,
    refetchInterval: 15_000,
    retry: false,
  });
  const profileQ = useQuery({
    queryKey: ["weltrade-profile"],
    queryFn: weltradeApi.profile,
    staleTime: 60_000,
    retry: false,
  });
  const registryQ = useQuery({
    queryKey: ["mt5-broker-registry"],
    queryFn: brokerConnectivityApi.mt5BrokerRegistry,
    staleTime: 60_000,
    retry: false,
  });

  const health = asRecord(healthQ.data);
  const mt5 = asRecord(mt5Q.data);
  const profile = asRecord(profileQ.data);
  const brokerOptions = useMemo(
    () => mapRegistryBrokers(asList(asRecord(registryQ.data).brokers)),
    [registryQ.data],
  );

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

  const [brokerSlug, setBrokerSlug] = useState<Mt5BrokerSlug | null>("weltrade");
  const [accountType, setAccountType] = useState<AccountType>("live");
  const [server, setServer] = useState("Weltrade-Real");
  const [serverQuery, setServerQuery] = useState("");
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [passwordFieldKey, setPasswordFieldKey] = useState(0);
  const [terminalPath, setTerminalPath] = useState("");
  const [progress, setProgress] = useState<string | null>(null);
  const [confirmLeave, setConfirmLeave] = useState(false);
  const [changingAccount, setChangingAccount] = useState(false);

  const selectedBroker =
    brokerOptions.find((b) => b.slug === brokerSlug) ??
    (brokerSlug ? brokerBySlug(brokerSlug) : undefined);

  const serversQ = useQuery({
    queryKey: ["mt5-servers", brokerSlug],
    queryFn: () => brokerConnectivityApi.mt5Servers(String(brokerSlug)),
    enabled: Boolean(brokerSlug),
    staleTime: 60_000,
    retry: false,
  });

  const apiServerRows = useMemo(() => {
    const rows = asList(asRecord(serversQ.data).servers);
    return rows
      .map((item) => {
        const row = asRecord(item);
        const name = str(row.name, "");
        if (!name) return null;
        const env = str(row.environment, "live").toLowerCase() === "demo" ? "demo" : "live";
        return {
          name,
          environment: env,
          source: str(row.source, "unknown"),
          verified_at: row.verified_at ? String(row.verified_at) : null,
        } satisfies Mt5ServerRow;
      })
      .filter((row): row is Mt5ServerRow => row !== null);
  }, [serversQ.data]);

  const profileServerList = useMemo(() => {
    const servers = asRecord(asRecord(profile).servers);
    const list = Array.isArray(servers[accountType])
      ? (servers[accountType] as string[])
      : [];
    return list.map(String).filter(Boolean);
  }, [profile, accountType]);

  const serverOptions = useMemo(() => {
    const base = serversForBroker(
      selectedBroker,
      accountType,
      selectedBroker?.slug === "weltrade" ? profileServerList : undefined,
      apiServerRows,
    );
    const q = serverQuery.trim().toLowerCase();
    if (!q) return base;
    return base.filter((s) => s.toLowerCase().includes(q));
  }, [selectedBroker, accountType, profileServerList, apiServerRows, serverQuery]);

  useEffect(() => {
    if (!serverOptions.includes(server)) {
      setServer(serverOptions[0] ?? "");
    }
  }, [serverOptions, server]);

  useEffect(() => {
    const liveLogin = str(mt5.login || session.login);
    if (liveLogin && liveLogin !== "—" && !login) setLogin(liveLogin);
    const liveServer = str(mt5.server || session.server);
    if (liveServer && liveServer !== "—") {
      setServer(liveServer);
      setAccountType(inferAccountType(liveServer));
      const matched = matchBrokerByServer(liveServer);
      if (matched) setBrokerSlug(matched.slug);
    }
    if (session.connected) setPassword("");
  }, [mt5.login, mt5.server, session.login, session.server, session.connected, login]);

  const refresh = async () => {
    await session.invalidateAll();
    await Promise.all([
      healthQ.refetch(),
      mt5Q.refetch(),
      exposureQ.refetch(),
    ]);
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
    setShowPassword(false);
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
        if (!cancelled && profileRow.server) {
          const srv = String(profileRow.server);
          setServer(srv);
          setAccountType(inferAccountType(srv));
          const matched = matchBrokerByServer(srv);
          if (matched) setBrokerSlug(matched.slug);
        }
        if (!cancelled && profileRow.terminal_path) {
          setTerminalPath(String(profileRow.terminal_path));
        }
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
      setChangingAccount(false);
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
      setChangingAccount(false);
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
        confirm_leave_exposure: confirmLeave,
      });
    },
    onMutate: () => {
      setProgress("CONNECTING");
    },
    onSuccess: async () => {
      clearPasswordField();
      toast.success("CONNECTED");
      setChangingAccount(false);
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

  const requestBusy =
    connectMut.isPending ||
    disconnectMut.isPending ||
    saveMut.isPending;

  const onConnect = () => {
    if (!selectedBroker) {
      toast.error("Select a broker");
      return;
    }
    if (!selectedBroker.connectable) {
      toast.error(
        `${selectedBroker.name} is not production-verified yet. Connect Weltrade, or wait for a verified Windows gateway worker for this broker.`,
      );
      return;
    }
    if (!server) {
      toast.error("Select server");
      return;
    }
    const loginNum = Number(login);
    if ((!Number.isFinite(loginNum) || loginNum <= 0) && !password) {
      void (async () => {
        setProgress("Verifying ownership…");
        try {
          await weltradeApi.claim();
          toast.success("Account ownership verified");
          await refresh();
          return;
        } catch {
          /* claim refused — try the persisted account next */
        }
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
      confirm_leave_exposure: confirmLeave,
    });
  };

  const claimMut = useMutation({
    mutationFn: weltradeApi.claim,
    onMutate: () => setProgress("Verifying ownership…"),
    onSuccess: async () => {
      toast.success("Account ownership verified");
      setChangingAccount(false);
      await qc.invalidateQueries({ queryKey: ["trading-session"] });
      await refresh();
      setProgress(null);
    },
    onError: (e) => {
      setProgress(null);
      toast.error(
        e instanceof ApiError
          ? traderFacingErrorMessage(e)
          : "CONNECTION_FAILED",
      );
    },
  });

  const busy = requestBusy || claimMut.isPending;
  const tradingSnap = tradingSnapEarly;
  const connectionView = resolveConnectionPresentation(tradingSnap, {
    connecting: Boolean(progress) || busy,
  });
  const uxState = str(
    tradingSnap.ux_state,
    connected ? "CONNECTED" : "NO_BROKER",
  );
  const showConnectForm = !connected || uxState === "SESSION_MISMATCH" || changingAccount;
  const exposure = asRecord(exposureQ.data);
  const exposureOpen = Number(exposure.open_positions ?? 0);
  const exposurePending = Number(exposure.pending_orders ?? 0);
  const exposureSymbols = Array.isArray(exposure.symbols)
    ? exposure.symbols.map((item) => String(item)).filter(Boolean)
    : [];
  const exposureNeedsConfirm =
    exposureQ.isSuccess && (exposureOpen > 0 || exposurePending > 0);

  const liveTradingHint = researchDeskLiveTradingStatus(
    connectionView,
    tradingSnap.trading,
    {
      liveTradingState: tradingSnap.live_trading_state,
      ordersMaySubmit: tradingSnap.orders_may_submit,
      liveAuthorization: tradingSnap.live_authorization,
    },
  );
  const isLiveAccount =
    inferAccountType(str(connectionView.server || server, "Weltrade-Real")) === "live";

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

  const connectedBroker =
    matchBrokerByServer(str(connectionView.server || server)) ||
    selectedBroker ||
    brokerBySlug("weltrade");

  const balanceDisplay =
    session.balance && session.balance !== "—"
      ? String(session.balance).replace(/^\$/, "")
      : "—";
  const currencyDisplay = str(tradingSnap.currency, "USD");
  const loginDisplay = connectionView.maskedLogin || login || "—";
  const tradingEnabled = liveTradingHint.label.toLowerCase().includes("enabled");

  const onBrokerPicked = (broker: Mt5BrokerOption) => {
    setBrokerSlug(broker.slug);
    setServerQuery("");
    const nextServers = serversForBroker(
      broker,
      accountType,
      broker.slug === "weltrade" ? profileServerList : undefined,
    );
    const next = nextServers[0] ?? "";
    setServer(next);
    if (next) setAccountType(inferAccountType(next));
  };

  return (
    <div className="mx-auto flex w-full min-w-0 max-w-3xl flex-col items-center px-1 py-2 sm:px-0 sm:py-4">
      <article
        className={cn(
          "w-full overflow-visible rounded-[1.35rem] border border-[color-mix(in_srgb,var(--accent)_18%,rgba(255,255,255,0.12))]",
          "bg-[color-mix(in_srgb,#071528_72%,transparent)] shadow-[0_0_0_1px_rgba(255,255,255,0.03),0_24px_80px_rgba(0,0,0,0.45)]",
          "backdrop-blur-[18px] px-5 py-7 sm:px-8 sm:py-9",
        )}
      >
        <header className="mb-7 flex flex-col items-center text-center">
          <Mt5BrandMark size={78} className="mb-4" />
          <h1 className="text-[1.65rem] font-semibold tracking-tight text-[var(--fg)] sm:text-[1.85rem]">
            Connect MT5 Account
          </h1>
          <p className="mt-2 max-w-md text-sm text-[var(--fg-muted)]">
            Link your existing MetaTrader 5 trading account to QuantForg in seconds.
          </p>
        </header>

        {connected && !showConnectForm ? (
          <div className="space-y-4">
            <div className="relative overflow-hidden rounded-2xl border border-[var(--border)] bg-[color-mix(in_srgb,var(--surface)_60%,transparent)] px-4 py-4 sm:px-5">
              <span className="absolute right-3 top-3 inline-flex items-center gap-1.5 rounded-full border border-[color-mix(in_srgb,var(--success)_40%,var(--border))] bg-[color-mix(in_srgb,var(--success)_12%,transparent)] px-2.5 py-1 text-[11px] font-semibold text-[var(--success)]">
                <span className="h-1.5 w-1.5 rounded-full bg-[var(--success)]" aria-hidden />
                Connected
              </span>
              <div className="flex items-start gap-3 pr-24">
                <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-[color-mix(in_srgb,var(--success)_35%,var(--border))] bg-[color-mix(in_srgb,var(--success)_10%,transparent)] text-[var(--success)]">
                  <CheckCircle2 className="h-5 w-5" aria-hidden />
                </span>
                <div>
                  <p className="text-base font-semibold text-[var(--fg)]">MT5 Account Connected</p>
                  <p className="mt-0.5 text-sm text-[var(--fg-muted)]">
                    Your trading account is now linked to QuantForg.
                  </p>
                </div>
              </div>
            </div>

            <div className="grid gap-2.5 sm:grid-cols-3">
              {(
                [
                  {
                    label: "Broker",
                    value: connectedBroker?.name || "MT5",
                    icon: connectedBroker ? (
                      <BrokerLogo
                        src={connectedBroker.logoSrc}
                        name={connectedBroker.name}
                        size={24}
                        rounded="full"
                      />
                    ) : (
                      <Building2 className="h-4 w-4 text-[var(--fg-subtle)]" aria-hidden />
                    ),
                  },
                  {
                    label: "Server",
                    value: connectionView.server || "—",
                    icon: <Server className="h-4 w-4 text-[var(--fg-subtle)]" aria-hidden />,
                  },
                  {
                    label: "MT5 Login",
                    value: loginDisplay,
                    icon: <UserRound className="h-4 w-4 text-[var(--fg-subtle)]" aria-hidden />,
                  },
                  {
                    label: "Account Balance",
                    value: balanceDisplay,
                    icon: <Wallet className="h-4 w-4 text-[var(--fg-subtle)]" aria-hidden />,
                  },
                  {
                    label: "Currency",
                    value: currencyDisplay,
                    icon: <Coins className="h-4 w-4 text-[var(--fg-subtle)]" aria-hidden />,
                  },
                  {
                    label: "Account Type",
                    value: isLiveAccount ? "Real / Live" : "Demo",
                    icon: <Layers className="h-4 w-4 text-[var(--fg-subtle)]" aria-hidden />,
                  },
                ] as const
              ).map((cell) => (
                <div
                  key={cell.label}
                  className="rounded-xl border border-[var(--border)] bg-[color-mix(in_srgb,var(--bg)_40%,transparent)] px-3.5 py-3"
                >
                  <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
                    {cell.label}
                  </p>
                  <div className="mt-2 flex min-w-0 items-center gap-2.5">
                    {cell.icon}
                    <span className="truncate text-sm font-medium text-[var(--fg)]">{cell.value}</span>
                  </div>
                </div>
              ))}
            </div>

            <div className="grid gap-2.5 sm:grid-cols-3">
              {(
                [
                  {
                    label: "Connection",
                    value: gatewayOnline || connected ? "Active" : "Offline",
                    ok: connected && gatewayOnline,
                  },
                  {
                    label: "Trading Permission",
                    value: tradingEnabled ? "Enabled" : liveTradingHint.label,
                    ok: tradingEnabled,
                  },
                  {
                    label: "Data Sync",
                    value: connected ? "Real-time" : "Idle",
                    ok: connected,
                  },
                ] as const
              ).map((row) => (
                <div
                  key={row.label}
                  className="rounded-xl border border-[var(--border)] bg-[color-mix(in_srgb,var(--bg)_40%,transparent)] px-3.5 py-3"
                >
                  <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
                    {row.label}
                  </p>
                  <div className="mt-2 flex items-center gap-2 text-sm font-medium">
                    {row.ok ? (
                      <CheckCircle2 className="h-4 w-4 shrink-0 text-[var(--success)]" aria-hidden />
                    ) : (
                      <span
                        className="inline-block h-2 w-2 shrink-0 rounded-full bg-[var(--fg-subtle)]"
                        aria-hidden
                      />
                    )}
                    <span className={row.ok ? "text-[var(--fg)]" : "text-[var(--fg-muted)]"}>
                      {row.value}
                    </span>
                  </div>
                </div>
              ))}
            </div>

            <p className="text-xs text-[var(--fg-subtle)]">
              Live trading: {liveTradingHint.label}
              {ownershipBlockMessage(tradingSnap.ownership_block_reason)
                ? ` · ${ownershipBlockMessage(tradingSnap.ownership_block_reason)}`
                : ""}
            </p>

            <div className="grid gap-2.5 sm:grid-cols-3">
              <Button
                variant="outline"
                disabled={busy}
                className="h-11 border-[color-mix(in_srgb,var(--accent)_28%,var(--border))] bg-transparent"
                onClick={() => setChangingAccount(true)}
              >
                <Pencil className="h-4 w-4" />
                Change account
              </Button>
              <Button
                variant="outline"
                disabled={busy}
                className="h-11 border-[color-mix(in_srgb,var(--accent)_40%,var(--border))] text-[var(--accent)] shadow-[0_0_18px_rgba(0,212,224,0.12)]"
                onClick={onReconnect}
              >
                <RefreshCw className="h-4 w-4" />
                Reconnect
              </Button>
              <Button
                variant="outline"
                disabled={busy}
                className="h-11 border-[color-mix(in_srgb,var(--danger)_45%,var(--border))] text-[var(--danger)] shadow-[0_0_18px_rgba(225,29,72,0.12)]"
                onClick={() => disconnectMut.mutate()}
              >
                <Unplug className="h-4 w-4" />
                Disconnect
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {uxState === "SESSION_MISMATCH" ? (
              <p className="rounded-xl border border-[color-mix(in_srgb,var(--warning)_40%,transparent)] bg-[var(--warning-soft)] px-3 py-2 text-sm text-[var(--warning)]">
                ACCOUNT SESSION MISMATCH. Reconnect your own account.
              </p>
            ) : null}

            {!connected && gatewayMt5Attached ? (
              <p className="rounded-xl border border-[color-mix(in_srgb,var(--warning)_35%,transparent)] bg-[var(--warning-soft)] px-3 py-2 text-xs text-[var(--warning)]">
                A gateway session may exist, but it is not your owned broker connection.
                Use Connect MT5 to claim ownership.
                {ownershipBlockMessage(tradingSnap.ownership_block_reason)
                  ? ` ${ownershipBlockMessage(tradingSnap.ownership_block_reason)}`
                  : ""}
              </p>
            ) : null}

            {selectedBroker && !selectedBroker.connectable ? (
              <p className="rounded-xl border border-[var(--border)] bg-[var(--surface-2)]/60 px-3 py-2 text-xs text-[var(--fg-muted)]">
                {selectedBroker.name} is listed for Demo/Live server discovery, but Connect stays
                disabled until a QuantForg Windows MT5 worker records a real authenticate+verify.
                Documented search hints are not selectable verified servers. Weltrade remains the
                production-verified path.
              </p>
            ) : null}
            {serversQ.isSuccess && !serverOptions.length && selectedBroker ? (
              <p className="text-[11px] text-[var(--fg-subtle)]">
                No verified {accountType} servers for {selectedBroker.name} yet
                {asList(asRecord(serversQ.data).documented_search_hints).length
                  ? ` · documented search hints available to operators (${asList(asRecord(serversQ.data).documented_search_hints).length})`
                  : ""}
                .
              </p>
            ) : null}

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <label className="text-[11px] font-medium text-[var(--fg-subtle)]">Broker</label>
                <BrokerSelect
                  value={brokerSlug}
                  options={brokerOptions.length ? brokerOptions : MT5_BROKER_OPTIONS}
                  disabled={busy}
                  onChange={onBrokerPicked}
                />
              </div>
              <div className="space-y-1.5">
                <label htmlFor="bw-server" className="text-[11px] font-medium text-[var(--fg-subtle)]">
                  Server
                </label>
                <div className="space-y-2">
                  <FieldShell>
                    <Search className="h-4 w-4 shrink-0 text-[var(--fg-subtle)]" aria-hidden />
                    <input
                      value={serverQuery}
                      disabled={busy}
                      onChange={(e) => setServerQuery(e.target.value)}
                      placeholder="Search verified servers..."
                      className="h-full w-full min-w-0 bg-transparent text-sm outline-none placeholder:text-[var(--fg-subtle)]"
                    />
                  </FieldShell>
                  <div className="relative">
                    <FieldShell>
                      <Server className="h-4 w-4 shrink-0 text-[var(--fg-subtle)]" aria-hidden />
                      <select
                        id="bw-server"
                        disabled={busy || !serverOptions.length}
                        className="h-full w-full min-w-0 appearance-none bg-transparent pr-6 text-sm outline-none disabled:opacity-60"
                        value={server}
                        onChange={(e) => {
                          const next = e.target.value;
                          setServer(next);
                          setAccountType(inferAccountType(next));
                        }}
                      >
                        {!serverOptions.length ? (
                          <option value="">No verified servers yet</option>
                        ) : !server ? (
                          <option value="">Select server</option>
                        ) : null}
                        {serverOptions.map((s) => {
                          const meta = apiServerRows.find((row) => row.name === s);
                          const tag =
                            meta?.environment === "demo" || inferAccountType(s) === "demo"
                              ? "Demo"
                              : "Live";
                          return (
                            <option
                              key={s}
                              value={s}
                              className="bg-[var(--bg-elevated)] text-[var(--fg)]"
                            >
                              {s} · {tag}
                            </option>
                          );
                        })}
                      </select>
                      <ChevronDown
                        className="pointer-events-none absolute right-3 h-4 w-4 text-[var(--fg-subtle)]"
                        aria-hidden
                      />
                    </FieldShell>
                  </div>
                </div>
              </div>
              <div className="space-y-1.5">
                <label htmlFor="bw-login" className="text-[11px] font-medium text-[var(--fg-subtle)]">
                  MT5 Login (Account Number)
                </label>
                <FieldShell>
                  <UserRound className="h-4 w-4 shrink-0 text-[var(--fg-subtle)]" aria-hidden />
                  <input
                    id="bw-login"
                    inputMode="numeric"
                    autoComplete="username"
                    disabled={busy}
                    value={login}
                    onChange={(e) => setLogin(e.target.value)}
                    placeholder="e.g. 81234567"
                    className="h-full w-full min-w-0 bg-transparent text-sm outline-none placeholder:text-[var(--fg-subtle)]"
                  />
                </FieldShell>
              </div>
              <div className="space-y-1.5">
                <label
                  htmlFor="bw-password"
                  className="text-[11px] font-medium text-[var(--fg-subtle)]"
                >
                  MT5 Password (Trading Password)
                </label>
                {showPasswordField ? (
                  <FieldShell>
                    <Lock className="h-4 w-4 shrink-0 text-[var(--fg-subtle)]" aria-hidden />
                    <input
                      key={passwordFieldKey}
                      id="bw-password"
                      type={showPassword ? "text" : "password"}
                      autoComplete="off"
                      name="broker-password"
                      disabled={busy}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Enter your MT5 password"
                      className="h-full w-full min-w-0 bg-transparent text-sm outline-none placeholder:text-[var(--fg-subtle)]"
                    />
                    <button
                      type="button"
                      className="text-[var(--fg-subtle)] hover:text-[var(--fg)]"
                      aria-label={showPassword ? "Hide password" : "Show password"}
                      onClick={() => setShowPassword((v) => !v)}
                    >
                      {showPassword ? (
                        <EyeOff className="h-4 w-4" aria-hidden />
                      ) : (
                        <Eye className="h-4 w-4" aria-hidden />
                      )}
                    </button>
                  </FieldShell>
                ) : (
                  <p className="flex h-12 items-center text-sm text-[var(--fg-subtle)]">
                    Password is never displayed after submission.
                  </p>
                )}
              </div>
            </div>

            {isOperator ? (
              <div className="space-y-1.5">
                <label htmlFor="bw-path" className="text-[11px] font-medium text-[var(--fg-subtle)]">
                  Terminal Path
                </label>
                <FieldShell>
                  <input
                    id="bw-path"
                    value={terminalPath}
                    onChange={(e) => setTerminalPath(e.target.value)}
                    placeholder="Optional — leave blank to auto-attach"
                    className="h-full w-full min-w-0 bg-transparent text-sm outline-none placeholder:text-[var(--fg-subtle)]"
                  />
                </FieldShell>
              </div>
            ) : null}

            {gatewayMt5Attached ? (
              <p className="text-sm text-[var(--fg-muted)]">
                {exposureQ.isError
                  ? "Open positions could not be read. The account will not be switched until exposure is verified."
                  : exposureQ.isLoading
                    ? "Reading open positions and pending orders…"
                    : exposureNeedsConfirm
                      ? `This terminal has ${exposureOpen} open position(s) and ${exposurePending} pending order(s)${exposureSymbols.length ? ` (${exposureSymbols.join(", ")})` : ""}. They stay at the broker and are not closed or moved.`
                      : "No open positions or pending orders on this terminal."}
              </p>
            ) : null}

            {gatewayMt5Attached && exposureNeedsConfirm ? (
              <label className="flex items-start gap-2 text-sm text-[var(--fg-muted)]">
                <input
                  type="checkbox"
                  className="mt-1"
                  checked={confirmLeave}
                  onChange={(e) => setConfirmLeave(e.target.checked)}
                />
                <span>
                  I understand open positions and pending orders stay on the current account.
                  They are not closed or moved. This terminal will trade only the account it
                  verifies next.
                </span>
              </label>
            ) : null}

            <div className="flex flex-col gap-2 pt-1">
              <Button
                className="qf-btn-hot h-12 w-full border-0 text-[15px] font-semibold text-[var(--brand-navy)]"
                disabled={busy || Boolean(selectedBroker && !selectedBroker.connectable)}
                onClick={onConnect}
              >
                {connectMut.isPending || saveMut.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Link2 className="h-4 w-4" />
                )}
                Connect MT5 Account
              </Button>
              {gatewayMt5Attached && !connected ? (
                <Button
                  variant="secondary"
                  disabled={busy}
                  className="h-11 w-full"
                  onClick={() => claimMut.mutate()}
                >
                  Claim ownership
                </Button>
              ) : null}
              {changingAccount && connected ? (
                <Button
                  variant="ghost"
                  disabled={busy}
                  className="h-10 w-full"
                  onClick={() => setChangingAccount(false)}
                >
                  Cancel change account
                </Button>
              ) : null}
            </div>

            {progress ? (
              <p className="flex items-center justify-center gap-2 text-sm text-[var(--accent)]">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                {progress}
              </p>
            ) : null}
          </div>
        )}

        <SecurityFooter />
        <p className="mt-3 text-center text-[11px] text-[var(--fg-subtle)]">
          Password is never displayed after submission. Connect MT5 uses your owned session only.
          {connected && !showConnectForm ? (
            <>
              {" "}
              <button
                type="button"
                className="text-[var(--fg-muted)] underline-offset-2 hover:underline"
                disabled={busy || session.refreshing}
                onClick={() => void refresh()}
              >
                <Link2Off className="mr-1 inline h-3 w-3" aria-hidden />
                Refresh status
              </button>
            </>
          ) : null}
        </p>
      </article>
    </div>
  );
}
