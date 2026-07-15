"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { toast } from "sonner";
import {
  Bell,
  BookOpen,
  Cloud,
  FileText,
  GraduationCap,
  LayoutTemplate,
  Network,
  NotebookPen,
  RefreshCw,
  Settings2,
  Sparkles,
  Star,
} from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { StatCard } from "@/components/dashboard/stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DeskEmpty, DeskError, DeskSkeleton, DeskTable } from "@/components/desk/primitives";
import { PageMotion, StaggerGrid, StaggerItem } from "@/components/desk/motion";
import { ecosystemApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, num, str } from "@/lib/desk";
import { formatNumber } from "@/lib/utils";

const MODULES = [
  { id: "journal", label: "Journal", icon: NotebookPen },
  { id: "playbooks", label: "Playbooks", icon: BookOpen },
  { id: "coach", label: "Coach", icon: Sparkles },
  { id: "watchlists", label: "Watchlists", icon: Star },
  { id: "workspaces", label: "Workspaces", icon: LayoutTemplate },
  { id: "alerts", label: "Alerts", icon: Bell },
  { id: "learning", label: "Learning", icon: GraduationCap },
  { id: "reports", label: "Reports", icon: FileText },
  { id: "settings", label: "Settings", icon: Settings2 },
  { id: "sync", label: "Cloud Sync", icon: Cloud },
] as const;

type ModuleId = (typeof MODULES)[number]["id"];

export default function EcosystemPage() {
  const qc = useQueryClient();
  const [module, setModule] = useState<ModuleId>("journal");
  const [journalQ, setJournalQ] = useState("");
  const [symbol, setSymbol] = useState("EURUSD");
  const [emotion, setEmotion] = useState("focused");
  const [lesson, setLesson] = useState("");
  const [playbookName, setPlaybookName] = useState("London Open Playbook");
  const [watchName, setWatchName] = useState("FX Majors");
  const [watchSymbols, setWatchSymbols] = useState("EURUSD,GBPUSD,USDJPY");
  const [wsName, setWsName] = useState("Research desk");
  const [period, setPeriod] = useState("weekly");
  const [tz, setTz] = useState("UTC");
  const [lastBundle, setLastBundle] = useState<Record<string, unknown> | null>(null);

  const hubQ = useQuery({
    queryKey: ["ecosystem-hub"],
    queryFn: ecosystemApi.hub,
    retry: false,
    staleTime: 15_000,
    refetchInterval: 60_000,
  });

  const journalQry = useQuery({
    queryKey: ["ecosystem-journal", journalQ],
    queryFn: () => ecosystemApi.journal(journalQ),
    retry: false,
    staleTime: 10_000,
    enabled: module === "journal",
  });

  const playbooksQ = useQuery({
    queryKey: ["ecosystem-playbooks"],
    queryFn: ecosystemApi.playbooks,
    retry: false,
    enabled: module === "playbooks",
  });

  const coachQ = useQuery({
    queryKey: ["ecosystem-coach"],
    queryFn: ecosystemApi.coach,
    retry: false,
    enabled: module === "coach",
    staleTime: 30_000,
  });

  const watchQ = useQuery({
    queryKey: ["ecosystem-watchlists"],
    queryFn: ecosystemApi.watchlists,
    retry: false,
    enabled: module === "watchlists",
  });

  const workspaceQ = useQuery({
    queryKey: ["ecosystem-workspaces"],
    queryFn: ecosystemApi.workspaces,
    retry: false,
    enabled: module === "workspaces",
  });

  const alertsQ = useQuery({
    queryKey: ["ecosystem-alerts"],
    queryFn: ecosystemApi.alerts,
    retry: false,
    enabled: module === "alerts",
  });

  const learningQ = useQuery({
    queryKey: ["ecosystem-learning"],
    queryFn: ecosystemApi.learning,
    retry: false,
    enabled: module === "learning",
  });

  const reportQ = useQuery({
    queryKey: ["ecosystem-reports", period],
    queryFn: () => ecosystemApi.reports(period),
    retry: false,
    enabled: module === "reports",
  });

  const prefsQ = useQuery({
    queryKey: ["ecosystem-preferences"],
    queryFn: ecosystemApi.preferences,
    retry: false,
    enabled: module === "settings",
  });

  const syncQ = useQuery({
    queryKey: ["ecosystem-sync"],
    queryFn: ecosystemApi.syncStatus,
    retry: false,
    enabled: module === "sync",
  });

  const invalidateHub = async () => {
    await qc.invalidateQueries({ queryKey: ["ecosystem-hub"] });
  };

  const ingest = useMutation({
    mutationFn: ecosystemApi.journalIngestPaper,
    onSuccess: async (data) => {
      toast.success(`Ingested ${num(data.created) || 0} paper stubs`);
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["ecosystem-journal"] }),
        invalidateHub(),
      ]);
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Ingest failed"),
  });

  const saveJournal = useMutation({
    mutationFn: () =>
      ecosystemApi.journalSave({
        symbol,
        emotion,
        emotion_notes: emotion,
        lessons_learned: lesson,
        tags: ["manual", "session"],
        screenshot_ref: null,
        market_context: { note: "User-authored context" },
        risk: { note: "Advisory — Decision Engine remains gatekeeper" },
      }),
    onSuccess: async () => {
      toast.success("Journal entry saved");
      setLesson("");
      await qc.invalidateQueries({ queryKey: ["ecosystem-journal"] });
      await invalidateHub();
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Save failed"),
  });

  const savePlaybook = useMutation({
    mutationFn: () =>
      ecosystemApi.playbookSave({
        name: playbookName,
        rules: ["Wait for Decision Engine ≠ WAIT", "Max 1% risk"],
        checklist: ["Session open", "Spread OK", "News clear"],
        psychology: ["No revenge trades", "Stop after 2 losses"],
        risk_rules: ["Hard daily stop", "No overlapping USD pairs"],
        sessions: ["London", "NY"],
        markets: ["EURUSD", "GBPUSD"],
      }),
    onSuccess: async () => {
      toast.success("Playbook saved");
      await qc.invalidateQueries({ queryKey: ["ecosystem-playbooks"] });
      await invalidateHub();
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Playbook save failed"),
  });

  const saveWatch = useMutation({
    mutationFn: () =>
      ecosystemApi.watchlistSave({
        name: watchName,
        category: "fx",
        symbols: watchSymbols.split(",").map((s) => s.trim().toUpperCase()).filter(Boolean),
        favorites: [watchSymbols.split(",")[0]?.trim().toUpperCase()].filter(Boolean),
        notes: { EURUSD: "Primary" },
      }),
    onSuccess: async () => {
      toast.success("Watchlist synced");
      await qc.invalidateQueries({ queryKey: ["ecosystem-watchlists"] });
      await invalidateHub();
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Watchlist save failed"),
  });

  const saveWs = useMutation({
    mutationFn: () =>
      ecosystemApi.workspaceSave({
        name: wsName,
        panels: ["chart", "journal", "decision"],
        widgets: ["watchlist", "alerts"],
        charts: [{ symbol: "EURUSD", timeframe: "H1" }],
        filters: { session: "London" },
        layout: { columns: 3 },
      }),
    onSuccess: async () => {
      toast.success("Workspace layout saved");
      await qc.invalidateQueries({ queryKey: ["ecosystem-workspaces"] });
      await invalidateHub();
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Workspace save failed"),
  });

  const createAlert = useMutation({
    mutationFn: () =>
      ecosystemApi.alertCreate({
        category: "decision",
        title: "Review Decision Engine",
        message: "Paper TRADE_IDEA — confirm playbook checklist before sizing",
        severity: "info",
      }),
    onSuccess: async () => {
      toast.success("Alert created");
      await qc.invalidateQueries({ queryKey: ["ecosystem-alerts"] });
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Alert failed"),
  });

  const completeLesson = useMutation({
    mutationFn: (id: string) => ecosystemApi.learningComplete(id),
    onSuccess: async () => {
      toast.success("Lesson marked complete");
      await qc.invalidateQueries({ queryKey: ["ecosystem-learning"] });
    },
  });

  const savePrefs = useMutation({
    mutationFn: () =>
      ecosystemApi.preferencesSave({ timezone: tz, theme: "dark" }),
    onSuccess: async () => {
      toast.success("Ecosystem preferences saved");
      await qc.invalidateQueries({ queryKey: ["ecosystem-preferences"] });
    },
  });

  const exportSync = useMutation({
    mutationFn: ecosystemApi.syncExport,
    onSuccess: async (data) => {
      setLastBundle(asRecord(data.bundle));
      toast.success("Cloud sync export ready");
      await qc.invalidateQueries({ queryKey: ["ecosystem-sync"] });
    },
  });

  const importSync = useMutation({
    mutationFn: () =>
      ecosystemApi.syncImport(lastBundle || {}),
    onSuccess: async () => {
      toast.success("Cloud sync imported");
      await invalidateHub();
      await qc.invalidateQueries({ queryKey: ["ecosystem-sync"] });
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Import failed"),
  });

  const hub = asRecord(hubQ.data);
  const preview = asRecord(hub.preview);
  const journalItems = asList(asRecord(journalQry.data).items).map(asRecord);
  const journalStats = asRecord(asRecord(journalQry.data).stats);
  const coach = asRecord(coachQ.data);
  const report = asRecord(reportQ.data);
  const prefs = asRecord(asRecord(prefsQ.data).preferences);

  return (
    <div className="ecosystem-desk">
      <PageHeader
        title="Ecosystem"
        description="Keep the full trading workflow in QuantForg — journal, playbooks, coach, watchlists, layouts, alerts, learning, and sync. Advisory-first. Decision Engine remains the gatekeeper."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" variant="secondary" onClick={() => hubQ.refetch()} disabled={hubQ.isFetching}>
              <RefreshCw className={`h-3.5 w-3.5 ${hubQ.isFetching ? "animate-spin" : ""}`} />
            </Button>
          </div>
        }
      />

      {hubQ.isLoading ? (
        <DeskSkeleton rows={8} />
      ) : (
        <PageMotion className="space-y-4">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <Badge tone="success">advisory only</Badge>
            <Badge tone="neutral">never_submits_orders</Badge>
            <Badge tone="neutral">DE gatekeeper</Badge>
            <Badge tone={hub.execution_enabled ? "danger" : "success"}>
              EXECUTION_ENABLED={String(Boolean(hub.execution_enabled))}
            </Badge>
            <span className="text-[var(--fg-subtle)]">
              v{str(hub.version, "1.0")} · {hubQ.isError ? "unavailable" : str(hub.status, "—")}
            </span>
          </div>

          {hubQ.isError && (
            <DeskError
              message="Ecosystem API unavailable — no fabricated workflow data."
              onRetry={() => hubQ.refetch()}
            />
          )}

          <StaggerGrid className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StaggerItem>
              <StatCard label="Journal" value={String(num(preview.journal_count) || 0)} />
            </StaggerItem>
            <StaggerItem>
              <StatCard label="Playbooks" value={String(num(preview.playbooks) || 0)} />
            </StaggerItem>
            <StaggerItem>
              <StatCard label="Watchlists" value={String(num(preview.watchlists) || 0)} />
            </StaggerItem>
            <StaggerItem>
              <StatCard label="Unread alerts" value={String(num(preview.unread_alerts) || 0)} />
            </StaggerItem>
          </StaggerGrid>

          <div
            className="flex gap-1 overflow-x-auto rounded-xl border border-[var(--border)] bg-[var(--surface)]/60 p-1.5 backdrop-blur"
            role="tablist"
            aria-label="Ecosystem modules"
          >
            {MODULES.map((m) => {
              const Icon = m.icon;
              const active = module === m.id;
              return (
                <button
                  key={m.id}
                  type="button"
                  role="tab"
                  aria-selected={active}
                  onClick={() => setModule(m.id)}
                  className={`flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-2 text-xs transition ${
                    active
                      ? "bg-[var(--surface-2)] text-[var(--fg)] shadow-sm"
                      : "text-[var(--fg-muted)] hover:bg-[var(--surface-2)]/50"
                  }`}
                >
                  <Icon className="h-3.5 w-3.5" />
                  {m.label}
                </button>
              );
            })}
          </div>

          <AnimatePresence mode="wait">
            <motion.div
              key={module}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.18 }}
              className="space-y-4"
            >
              {module === "journal" && (
                <div className="grid gap-4 xl:grid-cols-[300px_1fr]">
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">Automatic journal</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2">
                      <Button
                        size="sm"
                        className="w-full"
                        onClick={() => ingest.mutate()}
                        disabled={ingest.isPending}
                      >
                        Ingest DE paper ideas
                      </Button>
                      <Input
                        className="h-8 font-mono text-xs"
                        value={symbol}
                        onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                        aria-label="Symbol"
                      />
                      <Input
                        className="h-8 text-xs"
                        value={emotion}
                        onChange={(e) => setEmotion(e.target.value)}
                        placeholder="Emotion"
                      />
                      <Input
                        className="h-8 text-xs"
                        value={lesson}
                        onChange={(e) => setLesson(e.target.value)}
                        placeholder="Lessons learned"
                      />
                      <Button
                        size="sm"
                        variant="secondary"
                        className="w-full"
                        onClick={() => saveJournal.mutate()}
                        disabled={saveJournal.isPending}
                      >
                        Save entry
                      </Button>
                      <Input
                        className="h-8 text-xs"
                        value={journalQ}
                        onChange={(e) => setJournalQ(e.target.value)}
                        placeholder="Search tags / notes"
                      />
                      <p className="text-[11px] text-[var(--fg-subtle)]">
                        Fields: screenshots (ref), market context, DE score, AI review, risk,
                        emotion, lessons, tags — never auto-submits trades.
                      </p>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">
                        Entries · {journalStats.count == null ? "—" : String(journalStats.count)}
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      {journalQry.isLoading ? (
                        <DeskSkeleton rows={4} />
                      ) : journalItems.length === 0 ? (
                        <DeskEmpty
                          icon={NotebookPen}
                          title="No journal entries"
                          description="Ingest paper TRADE_IDEAs or save a manual review"
                        />
                      ) : (
                        <DeskTable
                          columns={["Symbol", "DE score", "Emotion", "Tags", "Lesson"]}
                          rows={journalItems.map((e) => [
                            str(e.symbol, "—"),
                            e.decision_engine_score == null
                              ? "—"
                              : formatNumber(num(e.decision_engine_score), 1),
                            str(e.emotion, "—"),
                            asList(e.tags).join(", ") || "—",
                            str(e.lessons_learned, "—").slice(0, 40),
                          ])}
                        />
                      )}
                    </CardContent>
                  </Card>
                </div>
              )}

              {module === "playbooks" && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Trading playbooks</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="flex flex-wrap gap-2">
                      <Input
                        className="h-8 max-w-xs text-xs"
                        value={playbookName}
                        onChange={(e) => setPlaybookName(e.target.value)}
                      />
                      <Button size="sm" onClick={() => savePlaybook.mutate()} disabled={savePlaybook.isPending}>
                        Save playbook
                      </Button>
                    </div>
                    {playbooksQ.isLoading ? (
                      <DeskSkeleton rows={3} />
                    ) : asList(asRecord(playbooksQ.data).items).length === 0 ? (
                      <DeskEmpty
                        icon={BookOpen}
                        title="No playbooks"
                        description="Create rules, checklist, psychology, risk, sessions, markets"
                      />
                    ) : (
                      <DeskTable
                        columns={["Name", "Sessions", "Markets", "Rules"]}
                        rows={asList(asRecord(playbooksQ.data).items)
                          .map(asRecord)
                          .map((p) => [
                            str(p.name),
                            asList(p.sessions).join(", ") || "—",
                            asList(p.markets).join(", ") || "—",
                            String(asList(p.rules).length),
                          ])}
                      />
                    )}
                  </CardContent>
                </Card>
              )}

              {module === "coach" && (
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-sm">
                      <Network className="h-4 w-4" /> Performance coach
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {coachQ.isLoading ? (
                      <DeskSkeleton rows={4} />
                    ) : str(coach.status) === "unavailable" ? (
                      <DeskEmpty
                        icon={Sparkles}
                        title="Coach waiting"
                        description={str(coach.reason, "Need journal or paper ideas")}
                      />
                    ) : (
                      <DeskTable
                        columns={["Topic", "Notes"]}
                        rows={[
                          ["Sample", String(num(coach.sample_size) || 0)],
                          ["Mistakes", asList(coach.common_mistakes).slice(0, 3).join(" · ")],
                          ["Habits", asList(coach.good_habits).slice(0, 3).join(" · ")],
                          ["Weaknesses", asList(coach.weaknesses).slice(0, 3).join(" · ")],
                          [
                            "Suggestions",
                            asList(coach.improvement_suggestions).slice(0, 3).join(" · "),
                          ],
                        ]}
                      />
                    )}
                    <p className="mt-2 text-[11px] text-[var(--fg-subtle)]">
                      Reviews last 100 trades from journal/paper — never bypasses Decision Engine.
                    </p>
                  </CardContent>
                </Card>
              )}

              {module === "watchlists" && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Cloud watchlists</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="flex flex-wrap gap-2">
                      <Input className="h-8 w-40 text-xs" value={watchName} onChange={(e) => setWatchName(e.target.value)} />
                      <Input
                        className="h-8 min-w-[200px] flex-1 font-mono text-xs"
                        value={watchSymbols}
                        onChange={(e) => setWatchSymbols(e.target.value)}
                      />
                      <Button size="sm" onClick={() => saveWatch.mutate()} disabled={saveWatch.isPending}>
                        Sync
                      </Button>
                    </div>
                    <DeskTable
                      columns={["Name", "Category", "Symbols", "Favorites"]}
                      rows={asList(asRecord(watchQ.data).items)
                        .map(asRecord)
                        .map((w) => [
                          str(w.name),
                          str(w.category),
                          asList(w.symbols).join(", "),
                          asList(w.favorites).join(", ") || "—",
                        ])}
                    />
                  </CardContent>
                </Card>
              )}

              {module === "workspaces" && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Saved workspaces</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="flex flex-wrap gap-2">
                      <Input className="h-8 max-w-xs text-xs" value={wsName} onChange={(e) => setWsName(e.target.value)} />
                      <Button size="sm" onClick={() => saveWs.mutate()} disabled={saveWs.isPending}>
                        Save layout
                      </Button>
                    </div>
                    <p className="text-[11px] text-[var(--fg-subtle)]">
                      Independent of Trading Terminal defaults — panels, charts, widgets, filters.
                    </p>
                    <DeskTable
                      columns={["Name", "Panels", "Widgets"]}
                      rows={asList(asRecord(workspaceQ.data).items)
                        .map(asRecord)
                        .map((w) => [
                          str(w.name),
                          asList(w.panels).join(", ") || "—",
                          asList(w.widgets).join(", ") || "—",
                        ])}
                    />
                  </CardContent>
                </Card>
              )}

              {module === "alerts" && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Ecosystem alerts</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="flex flex-wrap gap-2">
                      <Button size="sm" onClick={() => createAlert.mutate()} disabled={createAlert.isPending}>
                        Add decision alert
                      </Button>
                      <Button size="sm" variant="secondary" asChild>
                        <Link href="/notifications">Platform inbox</Link>
                      </Button>
                    </div>
                    <p className="text-[11px] text-[var(--fg-subtle)]">
                      Categories: price · risk · research · paper · decision
                    </p>
                    {asList(asRecord(alertsQ.data).items).length === 0 ? (
                      <DeskEmpty
                        icon={Bell}
                        title="No ecosystem alerts"
                        description="Create advisory alerts — never auto-trade"
                      />
                    ) : (
                      <DeskTable
                        columns={["Category", "Title", "Severity", "Read"]}
                        rows={asList(asRecord(alertsQ.data).items)
                          .map(asRecord)
                          .map((a) => [
                            str(a.category),
                            str(a.title),
                            str(a.severity),
                            a.read ? "yes" : "no",
                          ])}
                      />
                    )}
                  </CardContent>
                </Card>
              )}

              {module === "learning" && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Learning center</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <DeskTable
                      columns={["Guide", "Category", "Min", "Done"]}
                      rows={asList(asRecord(learningQ.data).catalog)
                        .map(asRecord)
                        .map((g) => {
                          const done = asList(asRecord(learningQ.data).completed).includes(
                            str(g.id),
                          );
                          return [
                            str(g.title),
                            str(g.category),
                            String(num(g.minutes) || "—"),
                            done ? "✓" : (
                              <Button
                                key={str(g.id)}
                                size="sm"
                                variant="secondary"
                                onClick={() => completeLesson.mutate(str(g.id))}
                              >
                                Complete
                              </Button>
                            ),
                          ];
                        })}
                    />
                  </CardContent>
                </Card>
              )}

              {module === "reports" && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Report center</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="flex flex-wrap gap-2">
                      {["daily", "weekly", "monthly", "quarterly"].map((p) => (
                        <Button
                          key={p}
                          size="sm"
                          variant={period === p ? "default" : "secondary"}
                          onClick={() => setPeriod(p)}
                        >
                          {p}
                        </Button>
                      ))}
                    </div>
                    {reportQ.isLoading ? (
                      <DeskSkeleton rows={3} />
                    ) : (
                      <>
                        <p className="text-sm">{str(report.title)}</p>
                        <DeskTable
                          columns={["Section", "Summary"]}
                          rows={[
                            [
                              "Journal",
                              JSON.stringify(asRecord(asRecord(report.sections).journal)).slice(
                                0,
                                120,
                              ),
                            ],
                            [
                              "Coach",
                              str(
                                asRecord(asRecord(report.sections).coach).status,
                                "—",
                              ),
                            ],
                            [
                              "Recommendations",
                              asList(asRecord(report.sections).recommendations)
                                .slice(0, 2)
                                .join(" · "),
                            ],
                          ]}
                        />
                        <p className="text-[11px] text-[var(--fg-subtle)]">
                          {str(report.disclaimer)}
                        </p>
                      </>
                    )}
                  </CardContent>
                </Card>
              )}

              {module === "settings" && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Professional preferences</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <p className="text-xs text-[var(--fg-subtle)]">
                      Ecosystem prefs (hotkeys, theme, layout, language, timezone). Platform
                      account security remains at{" "}
                      <Link className="underline" href="/settings">
                        /settings
                      </Link>
                      .
                    </p>
                    <Input
                      className="h-8 max-w-xs font-mono text-xs"
                      value={tz}
                      onChange={(e) => setTz(e.target.value)}
                      aria-label="Timezone"
                    />
                    <Button size="sm" onClick={() => savePrefs.mutate()} disabled={savePrefs.isPending}>
                      Save preferences
                    </Button>
                    <DeskTable
                      columns={["Key", "Value"]}
                      rows={Object.entries(prefs)
                        .filter(([k]) => k !== "hotkeys")
                        .map(([k, v]) => [k, v == null ? "—" : String(v)])}
                    />
                  </CardContent>
                </Card>
              )}

              {module === "sync" && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Cloud sync</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <p className="text-xs text-[var(--fg-subtle)]">
                      Synchronize watchlists, journal, playbooks, research refs, workspace
                      layouts — never broker positions or orders.
                    </p>
                    <div className="flex flex-wrap gap-2">
                      <Button size="sm" onClick={() => exportSync.mutate()} disabled={exportSync.isPending}>
                        Export bundle
                      </Button>
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => importSync.mutate()}
                        disabled={!lastBundle || importSync.isPending}
                      >
                        Re-import last export
                      </Button>
                    </div>
                    <DeskTable
                      columns={["Field", "Value"]}
                      rows={[
                        ["Status", str(asRecord(syncQ.data).status, "—")],
                        [
                          "Last sync",
                          str(asRecord(asRecord(syncQ.data).meta).last_sync_at, "—"),
                        ],
                        [
                          "Scopes",
                          asList(asRecord(syncQ.data).scopes).join(", ") || "—",
                        ],
                      ]}
                    />
                  </CardContent>
                </Card>
              )}
            </motion.div>
          </AnimatePresence>
        </PageMotion>
      )}
    </div>
  );
}
