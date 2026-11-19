"use client";

import {
  useEffect,
  useRef,
  useState,
  type ClipboardEvent,
  type ComponentType,
  type DragEvent,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import { useQuery } from "@tanstack/react-query";
import {
  BarChart3,
  Brain,
  CandlestickChart,
  ImagePlus,
  Layers3,
  Newspaper,
  Send,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskError } from "@/components/desk/primitives";
import { OverviewMarketIntelligence } from "@/components/trading/overview-market-intelligence";
import { AssistantMarkdown } from "@/components/trading/assistant-message";
import { intelligenceApi, mt5Api, strategyLabApi } from "@/lib/api/endpoints";
import {
  ASSISTANT_ACCEPTED,
  ASSISTANT_MAX_IMAGES,
  prepareChartImage,
} from "@/lib/assistant/image";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, num, str } from "@/lib/desk";
import { TRADING_SYMBOL } from "@/lib/trading/gold-only";
import { cn } from "@/lib/utils";

type DeskId = "assistant" | "insights" | "analysis" | "strategy" | "news";
type Msg = { role: "user" | "assistant"; content: string; images?: string[]; error?: boolean };

const DESKS: {
  id: DeskId;
  label: string;
  hint: string;
  icon: ComponentType<{ className?: string }>;
}[] = [
  {
    id: "assistant",
    label: "AI Assistant",
    hint: "Ask, analyze, and get trading answers",
    icon: Sparkles,
  },
  {
    id: "insights",
    label: "Market Insights",
    hint: "Real-time market trends and analysis",
    icon: BarChart3,
  },
  {
    id: "analysis",
    label: "Trade Analysis",
    hint: "Evaluate setups, entries, and risk",
    icon: CandlestickChart,
  },
  {
    id: "strategy",
    label: "Strategy Lab",
    hint: "Build and refine trading strategies",
    icon: Layers3,
  },
  {
    id: "news",
    label: "Market News",
    hint: "Key updates and economic events",
    icon: Newspaper,
  },
];

const PROMPTS = [
  "Analyze XAUUSD trend",
  "Where is gold heading today?",
  "Find a trade setup",
  "Review my risk settings",
  "Suggest a strategy",
  "Latest market news",
];

const DESK_NOTE: Record<DeskId, string> = {
  assistant:
    "Answers grounded in the live gold feed. Attach a chart screenshot for a full analysis. Advisory only — it never places trades.",
  insights: "XAUUSD structure from the live feed. Missing figures stay blank.",
  analysis: "Setups, exposure, and positions the intelligence service returned.",
  strategy: "Registered strategies only. The lab does not send orders.",
  news: "Headlines and calendar items from the connected feeds.",
};

export function IntelligenceHub() {
  const [desk, setDesk] = useState<DeskId>("assistant");
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [attachments, setAttachments] = useState<string[]>([]);
  const [dragging, setDragging] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const scrollerRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLElement>(null);
  const skipScroll = useRef(true);

  const dash = useQuery({
    queryKey: ["intelligence-dashboard"],
    queryFn: () => intelligenceApi.dashboard("FX"),
    retry: false,
    refetchInterval: 45_000,
    staleTime: 12_000,
  });
  const contextQ = useQuery({
    queryKey: ["intelligence-market-context"],
    queryFn: () => intelligenceApi.marketContext("FX"),
    retry: false,
    refetchInterval: 60_000,
    staleTime: 30_000,
    enabled: desk === "insights",
  });
  const tickQ = useQuery({
    queryKey: ["research-tick", TRADING_SYMBOL],
    queryFn: async () => {
      try {
        return await mt5Api.publicTick(TRADING_SYMBOL);
      } catch {
        return mt5Api.researchTick(TRADING_SYMBOL);
      }
    },
    retry: 1,
    staleTime: 5_000,
    refetchInterval: desk === "insights" ? 10_000 : false,
    enabled: desk === "insights",
  });
  const newsQ = useQuery({
    queryKey: ["intelligence-news"],
    queryFn: () => intelligenceApi.news(12),
    retry: false,
    staleTime: 30_000,
    enabled: desk === "news",
  });
  const calendarQ = useQuery({
    queryKey: ["intelligence-calendar"],
    queryFn: () => intelligenceApi.calendar(12),
    retry: false,
    staleTime: 30_000,
    enabled: desk === "news",
  });
  const registryQ = useQuery({
    queryKey: ["strategy-lab-registry"],
    queryFn: () => strategyLabApi.registry(),
    retry: false,
    staleTime: 30_000,
    enabled: desk === "strategy",
  });
  const labStatusQ = useQuery({
    queryKey: ["strategy-lab-status"],
    queryFn: () => strategyLabApi.status(),
    retry: false,
    staleTime: 30_000,
    enabled: desk === "strategy",
  });

  useEffect(() => {
    const el = scrollerRef.current;
    if (!el || desk !== "assistant") return;
    el.scrollTop = el.scrollHeight;
  }, [messages, busy, desk]);

  useEffect(() => {
    if (skipScroll.current) {
      skipScroll.current = false;
      return;
    }
    const panel = panelRef.current;
    if (!panel || !window.matchMedia("(max-width: 639px)").matches) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    panel.scrollIntoView({ block: "start", behavior: reduce ? "auto" : "smooth" });
  }, [desk]);

  async function addFiles(files: FileList | File[] | null) {
    const list = Array.from(files ?? []).filter((f) => f.type.startsWith("image/"));
    if (list.length === 0) return;
    const room = ASSISTANT_MAX_IMAGES - attachments.length;
    if (room <= 0) {
      toast.error(`You can attach up to ${ASSISTANT_MAX_IMAGES} images.`);
      return;
    }
    const ready: string[] = [];
    for (const file of list.slice(0, room)) {
      try {
        ready.push(await prepareChartImage(file));
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "The image could not be read.");
      }
    }
    if (ready.length) setAttachments((current) => [...current, ...ready].slice(0, ASSISTANT_MAX_IMAGES));
  }

  function onPaste(event: ClipboardEvent<HTMLTextAreaElement>) {
    const files = Array.from(event.clipboardData.files);
    if (files.some((f) => f.type.startsWith("image/"))) {
      event.preventDefault();
      void addFiles(files);
    }
  }

  function onDrop(event: DragEvent<HTMLElement>) {
    if (desk !== "assistant") return;
    event.preventDefault();
    setDragging(false);
    void addFiles(event.dataTransfer.files);
  }

  async function send(text: string) {
    const prompt = text.trim();
    const images = attachments;
    if ((!prompt && images.length === 0) || busy) return;
    const history = messages
      .filter((m) => !m.error)
      .slice(-12)
      .map((m) => ({ role: m.role, content: m.content }));
    setBusy(true);
    setMessages((current) => [
      ...current,
      { role: "user", content: prompt || "Analyze this chart.", images },
    ]);
    setInput("");
    setAttachments([]);
    try {
      const res = asRecord(
        await intelligenceApi.assistantChat({ message: prompt, history, images }),
      );
      const answer = str(res.answer, "");
      setMessages((current) => [
        ...current,
        answer
          ? { role: "assistant", content: answer }
          : { role: "assistant", content: "No answer was returned. Please try again.", error: true },
      ]);
    } catch (error) {
      const message = assistantErrorMessage(error);
      toast.error(message);
      setMessages((current) => [...current, { role: "assistant", content: message, error: true }]);
    } finally {
      setBusy(false);
    }
  }

  function onComposerKey(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void send(input);
    }
  }

  const data = asRecord(dash.data);
  const context = { ...asRecord(data.market_context), ...asRecord(contextQ.data) };
  const analysis = asRecord(data.analysis);
  const positions = asList(data.positions).map(asRecord);
  const pending = asList(data.pending_orders).map(asRecord);
  const spreads = asList(asRecord(data.market).spread_movers).map(asRecord);
  const tickEnvelope = asRecord(tickQ.data);
  const tick = asRecord(tickEnvelope.tick ?? tickQ.data);
  const bid = num(tick.bid);
  const ask = num(tick.ask);
  const tickMid =
    Number.isFinite(bid) && Number.isFinite(ask) ? (bid + ask) / 2 : Number.isFinite(bid) ? bid : ask;
  const active = DESKS.find((item) => item.id === desk) ?? DESKS[0];
  const ActiveIcon = active.icon;
  const ready = dash.isSuccess;

  return (
    <div className="qf-overview mx-auto flex w-full min-w-0 max-w-6xl flex-col gap-4">
      <header className="qf-overview-enter relative overflow-hidden">
        <svg className="qf-overview-wave" viewBox="0 0 480 120" fill="none" aria-hidden>
          <path d="M0 78C78 78 118 22 198 42s128 52 282-8" stroke="currentColor" strokeWidth="2.2" />
          <path d="M0 96C104 96 168 46 246 60s132 42 234-6" stroke="currentColor" strokeWidth="1.6" opacity="0.65" />
        </svg>
        <div className="relative z-[1] flex items-start gap-3">
          <span className="qf-overview-icon" aria-hidden>
            <Brain className="h-5 w-5" />
          </span>
          <div className="min-w-0">
            <h1 className="text-base font-semibold tracking-tight text-[var(--fg)] sm:text-lg">
              AI-powered trading insights, market analysis, and strategy intelligence.
            </h1>
            <p className="mt-1 max-w-3xl text-xs leading-relaxed text-[var(--fg-muted)] sm:text-sm">
              One desk for the assistant, the live gold market, trade notes, strategies, and news.
            </p>
          </div>
        </div>
      </header>

      <div className="grid grid-cols-2 items-stretch gap-3 sm:grid-cols-3 sm:gap-4 xl:grid-cols-5" role="tablist" aria-label="Intelligence desks">
        {DESKS.map((item, index) => {
          const Icon = item.icon;
          const selected = item.id === desk;
          return (
            <button
              key={item.id}
              type="button"
              role="tab"
              id={`intel-tab-${item.id}`}
              aria-selected={selected}
              aria-controls="intel-panel"
              className={cn(
                "qf-overview-card qf-overview-enter flex h-full min-h-[7.5rem] w-full flex-col items-start gap-3 p-3 text-left sm:min-h-[8.25rem] sm:p-4",
                "max-sm:[&:last-child:nth-child(odd)]:col-span-2",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]",
                selected && "ring-2 ring-[var(--accent)]",
              )}
              style={{ animationDelay: `${index * 40}ms` }}
              onClick={() => setDesk(item.id)}
            >
              <span className="qf-overview-icon qf-overview-icon-sm" aria-hidden>
                <Icon className="h-4 w-4" />
              </span>
              <span className="min-w-0">
                <span className="block text-sm font-semibold tracking-tight text-[var(--fg)]">{item.label}</span>
                <span className="mt-1 block text-xs leading-relaxed text-[var(--fg-muted)]">{item.hint}</span>
              </span>
            </button>
          );
        })}
      </div>

      <section
        ref={panelRef}
        id="intel-panel"
        role="tabpanel"
        aria-labelledby={`intel-tab-${desk}`}
        className={cn(
          "qf-overview-panel flex min-h-[36rem] flex-col lg:min-h-[calc(100dvh-18rem)]",
          dragging && desk === "assistant" && "ring-2 ring-[var(--accent)]",
        )}
        onDragOver={(event) => {
          if (desk !== "assistant") return;
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <div className="flex items-start justify-between gap-3 border-b border-[color-mix(in_srgb,var(--accent)_16%,var(--border))] px-4 py-3 sm:px-5">
          <div className="flex min-w-0 items-start gap-3">
            <span className="qf-overview-icon qf-overview-icon-sm" aria-hidden>
              <ActiveIcon className="h-4 w-4" />
            </span>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-sm font-semibold tracking-tight sm:text-base">{active.label}</h2>
                <Badge tone={dash.isError ? "warning" : ready ? "success" : "neutral"}>
                  {dash.isLoading ? "Checking" : dash.isError ? "Unavailable" : "Ready"}
                </Badge>
              </div>
              <p className="mt-1 text-xs leading-relaxed text-[var(--fg-muted)] sm:text-sm">{DESK_NOTE[desk]}</p>
            </div>
          </div>
          {desk === "assistant" && messages.length > 0 ? (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="h-10 w-10 shrink-0 px-0"
              aria-label="Clear conversation"
              onClick={() => setMessages([])}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          ) : null}
        </div>

        <div ref={scrollerRef} className="min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-6 sm:py-6">
          {desk === "assistant" ? (
            messages.length === 0 && !busy ? (
              <AssistantEmpty />
            ) : (
              <div className="mx-auto flex w-full max-w-3xl flex-col gap-3">
                {messages.map((message, index) =>
                  message.role === "user" ? (
                    <div key={`u-${index}`} className="ml-auto flex max-w-[min(100%,40rem)] flex-col items-end gap-2">
                      {message.images && message.images.length > 0 ? (
                        <div className="flex flex-wrap justify-end gap-2">
                          {message.images.map((src, i) => (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img
                              key={i}
                              src={src}
                              alt="Attached chart"
                              className="max-h-48 rounded-xl border border-[var(--border)] object-contain"
                            />
                          ))}
                        </div>
                      ) : null}
                      <p className="whitespace-pre-wrap rounded-2xl bg-[var(--accent)] px-3.5 py-2.5 text-sm leading-relaxed text-[var(--accent-fg)]">
                        {message.content}
                      </p>
                    </div>
                  ) : (
                    <div
                      key={`a-${index}`}
                      className={cn(
                        "mr-auto max-w-[min(100%,46rem)] rounded-2xl border px-4 py-3 text-[var(--fg)]",
                        message.error
                          ? "border-[color-mix(in_srgb,var(--warning)_45%,var(--border))] bg-[var(--surface-2)]"
                          : "border-[var(--border)] bg-[var(--surface-2)]",
                      )}
                    >
                      <AssistantMarkdown text={message.content} />
                    </div>
                  ),
                )}
                {busy ? (
                  <p className="mr-auto rounded-2xl border border-[var(--border)] bg-[var(--surface-2)] px-3.5 py-2.5 text-sm text-[var(--fg-muted)]">
                    Analyzing the live market…
                  </p>
                ) : null}
              </div>
            )
          ) : null}

          {desk === "insights" ? (
            <InsightsBody
              context={context}
              spreads={spreads}
              tickMid={tickMid}
              tick={tick}
              tickEnvelope={tickEnvelope}
              tickQ={tickQ}
              dash={dash}
            />
          ) : null}

          {desk === "analysis" ? (
            <AnalysisBody analysis={analysis} positions={positions} pending={pending} dash={dash} />
          ) : null}

          {desk === "strategy" ? (
            <StrategyBody registryQ={registryQ} statusQ={labStatusQ} />
          ) : null}

          {desk === "news" ? <NewsBody newsQ={newsQ} calendarQ={calendarQ} /> : null}
        </div>

        {desk === "assistant" ? (
          <div className="border-t border-[color-mix(in_srgb,var(--accent)_16%,var(--border))] px-3 py-3 sm:px-5 sm:py-4">
            <div className="mb-3 flex gap-2 overflow-x-auto pb-1 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
              {PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  className="shrink-0 rounded-full border border-[color-mix(in_srgb,var(--accent)_28%,var(--border))] bg-[var(--surface-2)] px-3 py-2 text-xs font-medium text-[var(--fg)] transition-colors duration-200 hover:border-[var(--accent)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] disabled:opacity-50"
                  disabled={busy}
                  onClick={() => void send(prompt)}
                >
                  {prompt}
                </button>
              ))}
            </div>
            {attachments.length > 0 ? (
              <div className="mb-2 flex flex-wrap gap-2">
                {attachments.map((src, i) => (
                  <div key={i} className="relative">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={src}
                      alt={`Chart ${i + 1}`}
                      className="h-16 w-24 rounded-lg border border-[var(--border)] object-cover"
                    />
                    <button
                      type="button"
                      aria-label="Remove image"
                      className="absolute -right-2 -top-2 grid h-6 w-6 place-items-center rounded-full bg-[var(--surface)] text-[var(--fg)] shadow ring-1 ring-[var(--border)]"
                      onClick={() => setAttachments((cur) => cur.filter((_, j) => j !== i))}
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            ) : null}
            <form
              className="flex items-end gap-2 rounded-2xl border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 focus-within:border-[var(--accent)]"
              onSubmit={(event: FormEvent) => {
                event.preventDefault();
                void send(input);
              }}
            >
              <input
                ref={fileRef}
                type="file"
                accept={ASSISTANT_ACCEPTED.join(",")}
                multiple
                className="hidden"
                onChange={(event) => {
                  void addFiles(event.target.files);
                  event.target.value = "";
                }}
              />
              <Button
                type="button"
                variant="ghost"
                className="h-11 w-11 shrink-0 px-0"
                aria-label="Attach chart screenshot"
                title="Attach chart screenshot"
                disabled={busy || attachments.length >= ASSISTANT_MAX_IMAGES}
                onClick={() => fileRef.current?.click()}
              >
                <ImagePlus className="h-4 w-4" />
              </Button>
              <label className="sr-only" htmlFor="intel-composer">
                Message to QuantForg AI
              </label>
              <textarea
                id="intel-composer"
                value={input}
                rows={1}
                disabled={busy}
                placeholder="Ask anything, or paste a chart screenshot…"
                className="max-h-32 min-h-11 flex-1 resize-none bg-transparent py-2.5 text-base leading-relaxed text-[var(--fg)] placeholder:text-[var(--fg-subtle)] focus:outline-none disabled:opacity-60"
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={onComposerKey}
                onPaste={onPaste}
              />
              <Button
                type="submit"
                className="h-11 w-11 shrink-0 px-0"
                aria-label="Send message"
                disabled={busy || (input.trim() === "" && attachments.length === 0)}
              >
                <Send className="h-4 w-4" />
              </Button>
            </form>
          </div>
        ) : null}
      </section>
    </div>
  );
}

function AssistantEmpty() {
  return (
    <div className="mx-auto flex min-h-[18rem] max-w-lg flex-col items-center justify-center px-4 text-center">
      <span className="qf-overview-icon h-16 w-16 rounded-2xl" aria-hidden>
        <Brain className="h-7 w-7" />
      </span>
      <h3 className="mt-5 text-xl font-semibold tracking-tight text-[var(--fg)] sm:text-2xl">Ask QuantForg AI</h3>
      <p className="mt-2 text-sm leading-relaxed text-[var(--fg-muted)] sm:text-base">
        Ask about gold, risk, strategy or the platform, in any language. Attach or paste a chart
        screenshot and QuantForg AI will read the structure, levels and scenarios against the live price.
      </p>
    </div>
  );
}

function InsightsBody({
  context,
  spreads,
  tickMid,
  tick,
  tickEnvelope,
  tickQ,
  dash,
}: {
  context: Record<string, unknown>;
  spreads: Record<string, unknown>[];
  tickMid: number;
  tick: Record<string, unknown>;
  tickEnvelope: Record<string, unknown>;
  tickQ: { isLoading: boolean; isError: boolean; dataUpdatedAt: number };
  dash: { isError: boolean; refetch: () => void };
}) {
  const facts = [
    ["Session", str(context.session, "")],
    ["Volatility", str(context.volatility_level, "")],
    ["Liquidity", str(context.liquidity_level, "")],
  ].filter(([, value]) => value && value !== "—");

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-4">
      {dash.isError ? (
        <DeskError message="Market intelligence could not be loaded." onRetry={() => dash.refetch()} />
      ) : null}
      <OverviewMarketIntelligence
        timeframe="M15"
        lastPrice={Number.isFinite(tickMid) ? tickMid : undefined}
        marketFeedStatus={str(tickEnvelope.status || (Number.isFinite(tickMid) ? "live" : "unavailable"))}
        tickUpdatedAt={tickQ.dataUpdatedAt || undefined}
        tickTime={str(tick.time || tick.timestamp || tickEnvelope.as_of || "")}
        tickLoading={tickQ.isLoading}
        tickError={tickQ.isError}
        support=""
        resistance=""
        confidencePct={null}
        signalDirection="WAIT"
      />
      {facts.length > 0 ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {facts.map(([label, value]) => (
            <div key={label} className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-3">
              <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">{label}</p>
              <p className="mt-1 truncate text-sm font-semibold text-[var(--fg)]">{value}</p>
            </div>
          ))}
        </div>
      ) : null}
      {spreads.length > 0 ? (
        <ul className="divide-y divide-[var(--border)] rounded-[var(--radius-os)] border border-[var(--border)]">
          {spreads.slice(0, 6).map((row, index) => (
            <li key={`${str(row.symbol)}-${index}`} className="flex items-center justify-between gap-3 px-3 py-2.5 text-sm">
              <span className="font-medium">{str(row.symbol, "Symbol")}</span>
              <span className="tabular text-[var(--fg-muted)]">
                {str(row.bid, "—")} / {str(row.ask, "—")} · {str(row.spread, "—")}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function AnalysisBody({
  analysis,
  positions,
  pending,
  dash,
}: {
  analysis: Record<string, unknown>;
  positions: Record<string, unknown>[];
  pending: Record<string, unknown>[];
  dash: { isLoading: boolean; isError: boolean; refetch: () => void };
}) {
  const groups = (
    [
      ["Market conditions", asList(analysis.market_conditions)],
      ["Risk factors", asList(analysis.risk_factors)],
      ["News impact", asList(analysis.news_impact)],
      ["Portfolio exposure", asList(analysis.portfolio_exposure)],
    ] as const
  ).filter(([, lines]) => lines.length > 0);

  if (dash.isLoading) return <p className="text-sm text-[var(--fg-muted)]">Loading trade analysis…</p>;
  if (dash.isError) return <DeskError message="Trade analysis could not be loaded." onRetry={() => dash.refetch()} />;
  if (groups.length === 0 && positions.length === 0 && pending.length === 0) {
    return (
      <p className="mx-auto max-w-md py-16 text-center text-sm leading-relaxed text-[var(--fg-muted)]">
        No trade analysis or open positions were returned.
      </p>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-5">
      {groups.length > 0 ? (
        <div className="grid gap-4 md:grid-cols-2">
          {groups.map(([title, lines]) => (
            <section key={title} className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface-2)] p-4">
              <h3 className="text-sm font-semibold">{title}</h3>
              <ul className="mt-2 space-y-1.5 text-sm leading-relaxed text-[var(--fg-muted)]">
                {lines.map((line, index) => (
                  <li key={index}>{String(line)}</li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      ) : null}
      {str(analysis.disclaimer, "") ? (
        <p className="text-xs leading-relaxed text-[var(--fg-subtle)]">{str(analysis.disclaimer, "")}</p>
      ) : null}
      {positions.length > 0 ? <TicketList title="Open positions" rows={positions} kind="position" /> : null}
      {pending.length > 0 ? <TicketList title="Pending orders" rows={pending} kind="order" /> : null}
    </div>
  );
}

function TicketList({
  title,
  rows,
  kind,
}: {
  title: string;
  rows: Record<string, unknown>[];
  kind: "position" | "order";
}) {
  return (
    <section>
      <h3 className="mb-2 text-sm font-semibold">{title}</h3>
      <ul className="divide-y divide-[var(--border)] rounded-[var(--radius-os)] border border-[var(--border)]">
        {rows.slice(0, 8).map((row, index) => {
          const pnl = num(row.profit);
          return (
            <li key={`${str(row.ticket, String(index))}`} className="flex items-center justify-between gap-3 px-3 py-2.5 text-sm">
              <span className="min-w-0 truncate font-medium">
                {str(row.symbol, "—")} · {str(kind === "position" ? row.side : row.order_type, "—")}
              </span>
              <span className="shrink-0 tabular text-[var(--fg-muted)]">
                {str(row.volume, "—")}
                {kind === "position" && Number.isFinite(pnl) ? (
                  <span className={pnl >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]"}> · {pnl.toFixed(2)}</span>
                ) : null}
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function StrategyBody({
  registryQ,
  statusQ,
}: {
  registryQ: { isLoading: boolean; isError: boolean; data: unknown; refetch: () => void };
  statusQ: { data: unknown };
}) {
  const status = asRecord(statusQ.data);
  const strategies = asList(asRecord(registryQ.data).strategies).map(asRecord);
  const mission = str(asRecord(status.config).mission, "");
  const disclaimer = str(status.disclaimer, "");

  if (registryQ.isLoading) return <p className="text-sm text-[var(--fg-muted)]">Loading Strategy Lab…</p>;
  if (registryQ.isError) {
    return <DeskError message="Strategy Lab could not be loaded." onRetry={() => registryQ.refetch()} />;
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-4">
      {mission ? <p className="text-sm leading-relaxed text-[var(--fg)]">{mission}</p> : null}
      {disclaimer ? <p className="text-xs leading-relaxed text-[var(--fg-subtle)]">{disclaimer}</p> : null}
      {strategies.length === 0 ? (
        <p className="py-16 text-center text-sm leading-relaxed text-[var(--fg-muted)]">
          No strategies are registered.
        </p>
      ) : (
        <ul className="divide-y divide-[var(--border)] rounded-[var(--radius-os)] border border-[var(--border)]">
          {strategies.slice(0, 12).map((row, index) => (
            <li key={`${str(row.key, String(index))}`} className="flex items-center justify-between gap-3 px-3 py-3">
              <span className="min-w-0">
                <span className="block truncate text-sm font-semibold">{str(row.name, "") || str(row.key, "Strategy")}</span>
                {str(row.name, "") && str(row.key, "") ? (
                  <span className="block truncate font-mono text-xs text-[var(--fg-muted)]">{str(row.key, "")}</span>
                ) : null}
              </span>
              {str(row.status, "") ? <Badge tone="neutral">{str(row.status, "")}</Badge> : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function NewsBody({
  newsQ,
  calendarQ,
}: {
  newsQ: { isLoading: boolean; isError: boolean; data: unknown; refetch: () => void };
  calendarQ: { isLoading: boolean; isError: boolean; data: unknown; refetch: () => void };
}) {
  if (newsQ.isLoading || calendarQ.isLoading) {
    return <p className="text-sm text-[var(--fg-muted)]">Loading the connected news and calendar feeds.</p>;
  }
  if (newsQ.isError && calendarQ.isError) {
    return (
      <DeskError
        message="The news and economic-calendar feeds could not be loaded. No headlines are shown in their place."
        onRetry={() => {
          newsQ.refetch();
          calendarQ.refetch();
        }}
      />
    );
  }
  const headlines = asList(newsQ.isError ? [] : newsQ.data).map(asRecord).filter((item) => str(item.title, ""));
  const events = asList(calendarQ.isError ? [] : calendarQ.data).map(asRecord).filter((item) => str(item.title, ""));
  if (headlines.length === 0 && events.length === 0) {
    return (
      <p className="mx-auto max-w-md py-16 text-center text-sm leading-relaxed text-[var(--fg-muted)]">
        No Gold or market headlines are available from the connected news and calendar feeds.
      </p>
    );
  }
  return (
    <div className="mx-auto grid w-full max-w-4xl gap-4 lg:grid-cols-2">
      {headlines.length > 0 ? (
        <ul className="divide-y divide-[var(--border)] rounded-[var(--radius-os)] border border-[var(--border)]">
          {headlines.slice(0, 8).map((item, index) => (
            <li key={`${str(item.title)}-${index}`} className="px-3 py-3">
              <p className="text-sm font-medium leading-relaxed">{str(item.title)}</p>
              <p className="mt-1 text-xs text-[var(--fg-muted)]">
                {[str(item.source, ""), str(item.published_at, "").slice(0, 16)].filter(Boolean).join(" · ")}
              </p>
            </li>
          ))}
        </ul>
      ) : null}
      {events.length > 0 ? (
        <ul className="divide-y divide-[var(--border)] rounded-[var(--radius-os)] border border-[var(--border)]">
          {events.slice(0, 8).map((item, index) => (
            <li key={`${str(item.title)}-${index}`} className="px-3 py-3">
              <p className="text-sm font-medium leading-relaxed">{str(item.title)}</p>
              <p className="mt-1 text-xs text-[var(--fg-muted)]">
                {[str(item.scheduled_at, "").slice(0, 16), str(item.country, ""), str(item.impact, "")]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function assistantErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const details = asRecord(error.details);
    const detail = asRecord(details.detail);
    const msg = str(detail.message, "") || str(asRecord(details.error).message, "");
    if (msg) return msg;
    if (error.status === 429) return "You've reached the assistant limit for now. Try again in a few minutes.";
    if (error.message && error.message !== "Request failed") return error.message;
  }
  return "QuantForg AI could not answer right now. Please try again.";
}
