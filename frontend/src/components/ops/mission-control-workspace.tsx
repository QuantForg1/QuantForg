"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Activity,
  AlertTriangle,
  LayoutTemplate,
  Search,
  ShieldAlert,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import {
  missionControlApi,
  mt5Api,
  portfolioApi,
} from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, num, str } from "@/lib/desk";
import { TRADING_SYMBOL } from "@/lib/trading/gold-only";
import { cn, formatNumber } from "@/lib/utils";

type PanelView = {
  panel_id: string;
  title: string;
  status: string;
  source: string;
  data: Record<string, unknown>;
  message: string;
};

function FeedEmpty({
  title,
  description,
}: {
  title: string;
  description?: string;
}) {
  return (
    <DeskEmpty
      icon={Activity}
      title={title}
      description={description?.trim() || "No live data from production feeds"}
    />
  );
}

function Panel({
  title,
  status,
  children,
  action,
  danger,
}: {
  title: string;
  status?: string;
  children: React.ReactNode;
  action?: React.ReactNode;
  danger?: boolean;
}) {
  return (
    <section
      className={cn(
        "border bg-[var(--surface)]",
        danger ? "border-[var(--danger)]/50" : "border-[var(--border)]",
      )}
    >
      <header className="flex items-center justify-between gap-2 border-b border-[var(--border)] px-3 py-2">
        <div className="flex items-center gap-2">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            {title}
          </h2>
          {status ? (
            <Badge
              tone={
                status === "available"
                  ? "success"
                  : status === "unavailable"
                    ? "warning"
                    : "neutral"
              }
              className="text-[9px] uppercase tracking-wider"
            >
              {status}
            </Badge>
          ) : null}
        </div>
        {action}
      </header>
      <div className="p-3">{children}</div>
    </section>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "danger" | "ok" | "muted";
}) {
  return (
    <div className="min-w-0">
      <div className="text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
        {label}
      </div>
      <div
        className={cn(
          "mt-0.5 truncate font-mono text-sm tabular-nums",
          tone === "danger" && "text-[var(--danger)]",
          tone === "ok" && "text-[var(--success)]",
          tone === "muted" && "text-[var(--fg-muted)]",
        )}
      >
        {value}
      </div>
    </div>
  );
}

function panelOf(
  dash: Record<string, unknown> | undefined,
  id: string,
): PanelView | null {
  const panels = asRecord(dash?.panels);
  const raw = asRecord(panels[id]);
  if (!raw.panel_id && !raw.title) return null;
  return {
    panel_id: str(raw.panel_id, id),
    title: str(raw.title, id),
    status: str(raw.status, "unavailable"),
    source: str(raw.source, ""),
    data: asRecord(raw.data),
    message: str(raw.message, ""),
  };
}

function fmtMoney(v: unknown): string {
  const n = num(v);
  if (!Number.isFinite(n)) return "—";
  return formatNumber(n, 2);
}

export function MissionControlWorkspace() {
  const qc = useQueryClient();
  const [noteText, setNoteText] = useState("");
  const [searchQ, setSearchQ] = useState("");
  const [searchHits, setSearchHits] = useState<Record<string, unknown>[]>([]);

  const accountQ = useQuery({
    queryKey: ["mission-control-mt5-account"],
    queryFn: () => mt5Api.account(),
    staleTime: 8_000,
    retry: false,
  });

  const positionsQ = useQuery({
    queryKey: ["mission-control-positions", TRADING_SYMBOL],
    queryFn: () => portfolioApi.positions(TRADING_SYMBOL),
    staleTime: 8_000,
    retry: false,
  });

  const tickQ = useQuery({
    queryKey: ["mission-control-tick", TRADING_SYMBOL],
    queryFn: () => mt5Api.tick(TRADING_SYMBOL),
    staleTime: 5_000,
    retry: false,
    refetchInterval: 10_000,
  });

  const liveFeeds = useMemo(() => {
    const capital =
      accountQ.data && !accountQ.isError
        ? {
            balance: accountQ.data.balance,
            equity: accountQ.data.equity,
            margin: accountQ.data.margin,
            free_margin: accountQ.data.margin_free ?? accountQ.data.free_margin,
            profit: accountQ.data.profit,
            currency: accountQ.data.currency,
            login: accountQ.data.login,
            server: accountQ.data.server,
          }
        : null;
    const positions =
      positionsQ.data && !positionsQ.isError
        ? (asList(positionsQ.data).map((row) => asRecord(row)) as Record<
            string,
            unknown
          >[])
        : null;
    const xauusd =
      tickQ.data && !tickQ.isError
        ? {
            symbol: TRADING_SYMBOL,
            bid: tickQ.data.bid,
            ask: tickQ.data.ask,
            last: tickQ.data.last,
            time: tickQ.data.time ?? tickQ.data.timestamp,
          }
        : null;
    return { capital, positions, xauusd };
  }, [accountQ.data, accountQ.isError, positionsQ.data, positionsQ.isError, tickQ.data, tickQ.isError]);

  const dashQ = useQuery({
    queryKey: [
      "mission-control-dashboard",
      liveFeeds.capital ? "cap" : "no-cap",
      liveFeeds.positions ? `pos-${liveFeeds.positions.length}` : "no-pos",
      liveFeeds.xauusd ? "tick" : "no-tick",
    ],
    queryFn: () =>
      missionControlApi.dashboardWithFeeds({
        capital: liveFeeds.capital,
        positions: liveFeeds.positions,
        xauusd: liveFeeds.xauusd,
      }),
    staleTime: 5_000,
    refetchInterval: 15_000,
  });

  const statusQ = useQuery({
    queryKey: ["mission-control-status"],
    queryFn: () => missionControlApi.status(),
    staleTime: 30_000,
  });

  const noteM = useMutation({
    mutationFn: () => missionControlApi.addNote({ text: noteText }),
    onSuccess: async () => {
      setNoteText("");
      toast.success("Note recorded");
      await qc.invalidateQueries({ queryKey: ["mission-control-dashboard"] });
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Note failed"),
  });

  const searchM = useMutation({
    mutationFn: (q: string) => missionControlApi.search(q),
    onSuccess: (data) => {
      setSearchHits(asList(asRecord(data).hits).map((h) => asRecord(h)));
      if (str(asRecord(data).status) === "empty") {
        toast.info(str(asRecord(data).message, "No matches"));
      }
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Search failed"),
  });

  const dash = asRecord(dashQ.data);
  const executive = panelOf(dash, "executive_status");
  const capital = panelOf(dash, "capital_overview");
  const risk = panelOf(dash, "risk_radar");
  const decisions = panelOf(dash, "live_ai_decisions");
  const positions = panelOf(dash, "live_positions");
  const incidents = panelOf(dash, "incident_center");
  const timeline = panelOf(dash, "production_timeline");
  const sysHealth = panelOf(dash, "system_health");
  const aiHealth = panelOf(dash, "ai_health");
  const emergency = panelOf(dash, "emergency_panel");
  const xau = panelOf(dash, "xauusd_watchlist");
  const daily = panelOf(dash, "daily_summary");
  const notes = panelOf(dash, "operator_notes");
  const fab = panelOf(dash, "floating_action_bar");

  const killArmed = Boolean(asRecord(emergency?.data).kill_switch);
  const caps = asRecord(statusQ.data?.capabilities);

  if (dashQ.isLoading && !dashQ.data) {
    return <DeskSkeleton rows={8} />;
  }
  if (dashQ.isError && !dashQ.data) {
    return (
      <DeskError
        message={
          dashQ.error instanceof ApiError
            ? dashQ.error.message
            : "Mission Control unavailable"
        }
      />
    );
  }

  return (
    <div className="relative space-y-3 pb-20">
      <div className="flex flex-wrap items-center gap-2 border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
        <LayoutTemplate className="size-4 text-[var(--fg-muted)]" />
        <span className="text-xs font-medium tracking-wide text-[var(--fg)]">
          Executive dashboard
        </span>
        <Badge tone="neutral" className="text-[9px] uppercase">
          Not Monitoring
        </Badge>
        {caps.fabricate_metrics === false ? (
          <Badge tone="accent" className="text-[9px] uppercase">
            Live feeds only
          </Badge>
        ) : null}
        <span className="ml-auto font-mono text-[10px] text-[var(--fg-subtle)]">
          {str(dash.generated_at, "—")}
        </span>
        <Button
          size="sm"
          variant="outline"
          onClick={() => void dashQ.refetch()}
        >
          Refresh
        </Button>
      </div>

      <div className="grid gap-3 xl:grid-cols-3">
        <Panel
          title="Executive Status"
          status={executive?.status}
          action={
            <Button asChild size="sm" variant="ghost">
              <Link href="/ops">Ops</Link>
            </Button>
          }
        >
          {!executive || executive.status === "unavailable" ? (
            <FeedEmpty title="Unavailable" description={executive?.message} />
          ) : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <Stat label="System" value={str(executive.data.system_status, "—")} />
              <Stat label="Mode" value={str(executive.data.execution_mode, "—")} />
              <Stat
                label="Kill switch"
                value={executive.data.kill_switch ? "ARMED" : "clear"}
                tone={executive.data.kill_switch ? "danger" : "ok"}
              />
              <Stat label="Gateway" value={str(executive.data.gateway_status, "—")} />
              <Stat label="MT5" value={str(executive.data.mt5_status, "—")} />
              <Stat
                label="OMS"
                value={executive.data.oms_orders_allowed ? "allowed" : "blocked"}
                tone={executive.data.oms_orders_allowed ? "ok" : "danger"}
              />
            </div>
          )}
        </Panel>

        <Panel title="Capital Overview" status={capital?.status}>
          {!capital || capital.status !== "available" ? (
            <FeedEmpty
              title={capital?.status === "empty" ? "Empty" : "No live feed"}
              description={capital?.message || "Connect MT5 for account equity"}
            />
          ) : (
            <div className="grid grid-cols-2 gap-3">
              <Stat label="Equity" value={fmtMoney(capital.data.equity)} />
              <Stat label="Balance" value={fmtMoney(capital.data.balance)} />
              <Stat label="Margin free" value={fmtMoney(capital.data.free_margin)} />
              <Stat label="Floating" value={fmtMoney(capital.data.profit)} />
            </div>
          )}
        </Panel>

        <Panel
          title="Risk Radar"
          status={risk?.status}
          action={
            <Button asChild size="sm" variant="ghost">
              <Link href="/risk">Risk desk</Link>
            </Button>
          }
        >
          {!risk || risk.status === "unavailable" ? (
            <FeedEmpty title="Unavailable" description={risk?.message} />
          ) : (
            <div className="grid grid-cols-2 gap-3">
              <Stat
                label="Risk status"
                value={str(risk.data.risk_status, "—")}
              />
              <Stat
                label="Risk / trade"
                value={`${str(risk.data.risk_per_trade_pct, "—")}%`}
              />
              <Stat
                label="Max daily loss"
                value={`${str(risk.data.max_daily_loss_pct, "—")}%`}
              />
              <Stat
                label="Max open"
                value={str(risk.data.max_open_trades, "—")}
              />
            </div>
          )}
        </Panel>
      </div>

      <div className="grid gap-3 xl:grid-cols-2">
        <Panel
          title="Live AI Decisions"
          status={decisions?.status}
          action={
            <Button asChild size="sm" variant="ghost">
              <Link href="/decision-intelligence">Decision Center</Link>
            </Button>
          }
        >
          {!decisions || decisions.status !== "available" ? (
            <FeedEmpty
              title={decisions?.status === "empty" ? "No decisions" : "Unavailable"}
              description={decisions?.message}
            />
          ) : (
            <ul className="max-h-48 space-y-1.5 overflow-auto font-mono text-[11px]">
              {asList(decisions.data.decisions).map((row, i) => {
                const r = asRecord(row);
                return (
                  <li
                    key={str(r.audit_id, String(i))}
                    className="flex justify-between gap-2 border-b border-[var(--border)]/60 py-1"
                  >
                    <span>{str(r.decision, "—")}</span>
                    <span className="text-[var(--fg-subtle)]">
                      {str(r.audit_id, str(r.strategy_id, ""))}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>

        <Panel title="Live Positions" status={positions?.status}>
          {!positions || positions.status !== "available" ? (
            <FeedEmpty
              title={positions?.status === "empty" ? "Flat" : "No live feed"}
              description={positions?.message}
            />
          ) : (
            <ul className="max-h-48 space-y-1.5 overflow-auto font-mono text-[11px]">
              {asList(positions.data.positions).map((row, i) => {
                const r = asRecord(row);
                return (
                  <li
                    key={str(r.ticket ?? r.id, String(i))}
                    className="flex justify-between gap-2 border-b border-[var(--border)]/60 py-1"
                  >
                    <span>
                      {str(r.symbol, TRADING_SYMBOL)} {str(r.side ?? r.type, "")}{" "}
                      {str(r.volume ?? r.lots, "")}
                    </span>
                    <span>{fmtMoney(r.profit ?? r.unrealized_pnl)}</span>
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>
      </div>

      <div className="grid gap-3 xl:grid-cols-2">
        <Panel
          title="Incident Center"
          status={incidents?.status}
          action={
            <Button asChild size="sm" variant="ghost">
              <Link href="/ops">Reliability</Link>
            </Button>
          }
        >
          {!incidents || incidents.status !== "available" ? (
            <FeedEmpty
              title={incidents?.status === "empty" ? "Clear" : "Unavailable"}
              description={incidents?.message}
            />
          ) : (
            <ul className="max-h-44 space-y-1.5 overflow-auto text-[11px]">
              {asList(incidents.data.incidents).map((row, i) => {
                const r = asRecord(row);
                return (
                  <li
                    key={str(r.id, String(i))}
                    className="border-b border-[var(--border)]/60 py-1"
                  >
                    <div className="flex justify-between gap-2 font-mono">
                      <span>{str(r.severity, "—")}</span>
                      <span className="text-[var(--fg-subtle)]">
                        {str(r.status, "")}
                      </span>
                    </div>
                    <div className="text-[var(--fg-muted)]">{str(r.title, "")}</div>
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>

        <Panel title="Production Timeline" status={timeline?.status}>
          {!timeline || timeline.status !== "available" ? (
            <FeedEmpty
              title={timeline?.status === "empty" ? "Quiet" : "Unavailable"}
              description={timeline?.message}
            />
          ) : (
            <ul className="max-h-44 space-y-1 overflow-auto font-mono text-[10px]">
              {asList(timeline.data.events).map((row, i) => {
                const r = asRecord(row);
                return (
                  <li key={str(r.id, String(i))} className="truncate py-0.5">
                    <span className="text-[var(--fg-subtle)]">
                      {str(r.timestamp, "").slice(11, 19)}
                    </span>{" "}
                    {str(r.category, "")}/{str(r.action, "")} —{" "}
                    {str(r.detail, "").slice(0, 80)}
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>
      </div>

      <div className="grid gap-3 xl:grid-cols-3">
        <Panel
          title="System Health"
          status={sysHealth?.status}
          action={
            <Button asChild size="sm" variant="ghost">
              <Link href="/monitoring">Monitoring</Link>
            </Button>
          }
        >
          {!sysHealth || sysHealth.status === "unavailable" ? (
            <FeedEmpty title="Unavailable" description={sysHealth?.message} />
          ) : (
            <div className="space-y-2">
              <div className="grid grid-cols-2 gap-3">
                <Stat label="Gateway" value={str(sysHealth.data.gateway_status, "—")} />
                <Stat label="MT5" value={str(sysHealth.data.mt5_status, "—")} />
                <Stat
                  label="Health score"
                  value={str(sysHealth.data.health_score, "—")}
                />
                <Stat label="Mode" value={str(sysHealth.data.execution_mode, "—")} />
              </div>
              <p className="text-[10px] text-[var(--fg-subtle)]">
                {sysHealth.message ||
                  "Executive posture — execution strip lives on Monitoring"}
              </p>
            </div>
          )}
        </Panel>

        <Panel title="AI Health" status={aiHealth?.status}>
          {!aiHealth || aiHealth.status !== "available" ? (
            <FeedEmpty title="Unavailable" description={aiHealth?.message} />
          ) : (
            <ul className="space-y-1 text-[11px]">
              {Object.entries(asRecord(aiHealth.data.modules)).map(([name, body]) => (
                <li
                  key={name}
                  className="flex justify-between border-b border-[var(--border)]/60 py-1 font-mono"
                >
                  <span>{name.replace(/_/g, " ")}</span>
                  <span className="text-[var(--success)]">
                    {asRecord(body).ok ? "online" : "—"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel
          title="Emergency Panel"
          status={emergency?.status}
          danger={killArmed}
          action={
            <Button asChild size="sm" variant={killArmed ? "danger" : "outline"}>
              <Link href="/ops">
                <ShieldAlert className="mr-1 size-3.5" />
                Ops control
              </Link>
            </Button>
          }
        >
          {!emergency || emergency.status === "unavailable" ? (
            <FeedEmpty title="Unavailable" description={emergency?.message} />
          ) : (
            <div className="space-y-2">
              <div className="grid grid-cols-2 gap-3">
                <Stat
                  label="Kill switch"
                  value={killArmed ? "ARMED" : "clear"}
                  tone={killArmed ? "danger" : "ok"}
                />
                <Stat
                  label="Auto trading"
                  value={str(emergency.data.auto_trading_status, "—")}
                />
                <Stat label="System" value={str(emergency.data.system_status, "—")} />
                <Stat
                  label="OMS"
                  value={emergency.data.oms_orders_allowed ? "allowed" : "blocked"}
                  tone={emergency.data.oms_orders_allowed ? "ok" : "danger"}
                />
              </div>
              <p className="flex items-start gap-1.5 text-[10px] text-[var(--fg-subtle)]">
                <AlertTriangle className="mt-0.5 size-3 shrink-0" />
                {emergency.message}
              </p>
            </div>
          )}
        </Panel>
      </div>

      <div className="grid gap-3 xl:grid-cols-3">
        <Panel title="XAUUSD Watchlist" status={xau?.status}>
          {!xau || xau.status !== "available" ? (
            <FeedEmpty
              title="No live tick"
              description={xau?.message || "Awaiting MT5 tick"}
            />
          ) : (
            <div className="grid grid-cols-2 gap-3">
              <Stat label="Symbol" value={str(xau.data.symbol, TRADING_SYMBOL)} />
              <Stat label="Bid" value={fmtMoney(xau.data.bid)} />
              <Stat label="Ask" value={fmtMoney(xau.data.ask)} />
              <Stat label="Last" value={fmtMoney(xau.data.last)} />
            </div>
          )}
        </Panel>

        <Panel title="Daily Summary" status={daily?.status}>
          {!daily || daily.status !== "available" ? (
            <FeedEmpty title="No inputs" description={daily?.message} />
          ) : (
            <div className="space-y-2 text-[11px]">
              {daily.data.decision_counts ? (
                <div className="flex flex-wrap gap-2 font-mono">
                  {Object.entries(asRecord(daily.data.decision_counts)).map(
                    ([k, v]) => (
                      <Badge key={k} tone="neutral">
                        {k}: {String(v)}
                      </Badge>
                    ),
                  )}
                </div>
              ) : null}
              <div className="grid grid-cols-2 gap-2">
                <Stat
                  label="Decision events"
                  value={str(daily.data.decision_events, "—")}
                />
                <Stat
                  label="Open incidents"
                  value={str(daily.data.open_incidents, "—")}
                />
                <Stat label="Mode" value={str(daily.data.execution_mode, "—")} />
                <Stat
                  label="Kill"
                  value={daily.data.kill_switch ? "ARMED" : "clear"}
                />
              </div>
              <p className="text-[10px] text-[var(--fg-subtle)]">{daily.message}</p>
            </div>
          )}
        </Panel>

        <Panel title="Operator Notes" status={notes?.status}>
          <div className="space-y-2">
            <textarea
              value={noteText}
              onChange={(e) => setNoteText(e.target.value)}
              rows={3}
              placeholder="Auditable operator note…"
              className="w-full border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5 text-xs outline-none focus:border-[var(--fg-muted)]"
            />
            <Button
              size="sm"
              disabled={!noteText.trim() || noteM.isPending}
              onClick={() => noteM.mutate()}
            >
              Record note
            </Button>
            {!notes || notes.status !== "available" ? (
              <FeedEmpty title="No notes" description={notes?.message} />
            ) : (
              <ul className="max-h-36 space-y-1.5 overflow-auto text-[11px]">
                {asList(notes.data.notes).map((row) => {
                  const r = asRecord(row);
                  return (
                    <li
                      key={str(r.note_id)}
                      className="border-b border-[var(--border)]/60 py-1"
                    >
                      <div className="font-mono text-[10px] text-[var(--fg-subtle)]">
                        {str(r.operator)} · {str(r.created_at).slice(0, 19)}
                      </div>
                      <div>{str(r.text)}</div>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </Panel>
      </div>

      <Panel
        title="Global Search"
        status="available"
        action={<Search className="size-3.5 text-[var(--fg-subtle)]" />}
      >
        <form
          className="flex flex-wrap gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (searchQ.trim()) searchM.mutate(searchQ.trim());
          }}
        >
          <input
            value={searchQ}
            onChange={(e) => setSearchQ(e.target.value)}
            placeholder="Search desks, notes, timeline…"
            className="min-w-[220px] flex-1 border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5 text-xs outline-none focus:border-[var(--fg-muted)]"
          />
          <Button size="sm" type="submit" disabled={searchM.isPending}>
            Search
          </Button>
        </form>
        {searchHits.length === 0 ? (
          <p className="mt-2 text-[10px] text-[var(--fg-subtle)]">
            Live search across Mission Control desks, operator notes, and
            production timeline events.
          </p>
        ) : (
          <ul className="mt-2 max-h-40 space-y-1 overflow-auto text-[11px]">
            {searchHits.map((h, i) => (
              <li key={`${str(h.href)}-${i}`}>
                <Link
                  href={str(h.href, "/mission-control")}
                  className="flex justify-between gap-2 border-b border-[var(--border)]/60 py-1 hover:text-[var(--fg)]"
                >
                  <span>
                    <span className="font-mono text-[10px] text-[var(--fg-subtle)]">
                      {str(h.kind)}
                    </span>{" "}
                    {str(h.title)}
                  </span>
                  <span className="truncate text-[var(--fg-muted)]">
                    {str(h.detail)}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <div className="fixed inset-x-0 bottom-0 z-40 border-t border-[var(--border)] bg-[var(--surface)]/95 backdrop-blur-sm">
        <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-2 px-3 py-2">
          <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Actions
          </span>
          {asList(fab?.data.actions).map((row) => {
            const a = asRecord(row);
            const danger = str(a.tone) === "danger";
            return (
              <Button
                key={str(a.href) + str(a.label)}
                asChild
                size="sm"
                variant={danger ? "danger" : "outline"}
              >
                <Link href={str(a.href, "/mission-control")}>{str(a.label)}</Link>
              </Button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
