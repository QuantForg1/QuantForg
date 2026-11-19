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
import {
  BarChart3,
  Brain,
  CandlestickChart,
  Check,
  Copy,
  ImagePlus,
  Layers3,
  Newspaper,
  Send,
  Sparkles,
  Square,
  Trash2,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { AnalysisTrace, TypewriterMarkdown } from "@/components/trading/assistant-trace";
import {
  AnalysisDesk,
  InsightsDesk,
  NewsDesk,
  StrategyDesk,
  useMarketDesk,
} from "@/components/trading/intelligence-desks";
import { intelligenceApi } from "@/lib/api/endpoints";
import { formatPrice, formatUtcTime } from "@/lib/assistant/desk-format";
import { settleStages, upsertStage } from "@/lib/assistant/stages";
import {
  AssistantStreamError,
  streamAssistant,
  type AssistantMeta,
  type AssistantStage,
} from "@/lib/assistant/stream";
import {
  ASSISTANT_ACCEPTED,
  ASSISTANT_MAX_IMAGES,
  prepareChartImage,
} from "@/lib/assistant/image";
import { ApiError } from "@/lib/api/client";
import { asRecord, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

type DeskId = "assistant" | "insights" | "analysis" | "strategy" | "news";
type Msg = {
  role: "user" | "assistant";
  content: string;
  images?: string[];
  error?: boolean;
  streaming?: boolean;
  meta?: AssistantMeta;
  /** Live analysis trace (assistant messages produced this session). */
  stages?: AssistantStage[];
  thinking?: string;
  startedAt?: number;
  endedAt?: number;
  /** Type the answer out (true for answers produced in this session). */
  live?: boolean;
  /** Typewriter has revealed the full answer. */
  typed?: boolean;
};

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
  "Where is gold heading today?",
  "Key support and resistance now",
  "Is now a good time to trade?",
  "Review my risk settings",
  "What news could move gold?",
];

const DESK_NOTE: Record<DeskId, string> = {
  assistant:
    "Answers grounded in the live gold feed. Attach a chart screenshot for a full analysis. Advisory only — it never places trades.",
  insights: "Live XAUUSD trend, momentum and key levels on M15, H1 and H4. Refreshes every 20 seconds.",
  analysis: "Is now a reasonable moment to trade gold? Seven measured checks, plus your open positions.",
  strategy: "100+ strategies tested on real gold data and ranked by their results.",
  news: "Economic calendar with countdowns and the latest headlines from the connected feeds.",
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

  const deskQ = useMarketDesk(desk !== "assistant");
  const abortRef = useRef<AbortController | null>(null);
  const [copied, setCopied] = useState<number | null>(null);

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

  function askFromDesk(prompt: string) {
    setDesk("assistant");
    void send(prompt);
  }

  function updateLast(patch: (m: Msg) => Msg) {
    setMessages((current) => {
      if (current.length === 0) return current;
      const next = current.slice();
      next[next.length - 1] = patch(next[next.length - 1]);
      return next;
    });
  }

  async function send(text: string) {
    const prompt = text.trim();
    const images = attachments;
    if ((!prompt && images.length === 0) || busy) return;
    const history = messages
      .filter((m) => !m.error && !m.streaming)
      .slice(-12)
      .map((m) => ({ role: m.role, content: m.content }));
    const body = { message: prompt, history, images };
    setBusy(true);
    setMessages((current) => [
      ...current,
      { role: "user", content: prompt || "Analyze this chart.", images },
      {
        role: "assistant",
        content: "",
        streaming: true,
        live: true,
        stages: [],
        thinking: "",
        startedAt: Date.now(),
      },
    ]);
    setInput("");
    setAttachments([]);
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      try {
        await streamAssistant(
          body,
          {
            onMeta: (meta) => updateLast((m) => ({ ...m, meta })),
            onStage: (stage) => updateLast((m) => ({ ...m, stages: upsertStage(m.stages ?? [], stage) })),
            onThinking: (text) => updateLast((m) => ({ ...m, thinking: (m.thinking ?? "") + text })),
            onDelta: (delta) =>
              updateLast((m) => ({
                ...m,
                content: m.content + delta,
                endedAt: m.endedAt ?? Date.now(),
              })),
          },
          controller.signal,
        );
        updateLast((m) => ({ ...m, streaming: false, stages: settleStages(m.stages ?? []) }));
      } catch (error) {
        if (controller.signal.aborted) {
          updateLast((m) => ({
            ...m,
            streaming: false,
            stages: settleStages(m.stages ?? []),
            endedAt: m.endedAt ?? Date.now(),
            content: m.content || "Stopped.",
          }));
          return;
        }
        // Streaming unavailable before any text (proxy, expired session…):
        // fall back to the regular endpoint, which refreshes the session.
        const fallback =
          error instanceof AssistantStreamError &&
          error.beforeFirstToken &&
          (error.status === 0 || error.status === 401 || error.status >= 500 || error.code === "interrupted");
        if (!fallback && !(error instanceof TypeError)) throw error;
        const res = asRecord(await intelligenceApi.assistantChat(body));
        const answer = str(res.answer, "");
        if (!answer) throw new Error("No answer was returned. Please try again.");
        updateLast((m) => ({
          ...m,
          content: answer,
          streaming: false,
          stages: settleStages(m.stages ?? []),
          endedAt: m.endedAt ?? Date.now(),
          meta: asRecord(res.meta) as AssistantMeta,
        }));
      }
    } catch (error) {
      const message = assistantErrorMessage(error);
      toast.error(message);
      updateLast((m) =>
        m.content
          ? { ...m, streaming: false, stages: settleStages(m.stages ?? []), content: `${m.content}\n\n(${message})` }
          : { ...m, streaming: false, stages: settleStages(m.stages ?? []), error: true, live: false, content: message },
      );
    } finally {
      abortRef.current = null;
      setBusy(false);
    }
  }

  async function copyAnswer(index: number, content: string) {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(index);
      window.setTimeout(() => setCopied(null), 1500);
    } catch {
      toast.error("Could not copy.");
    }
  }

  function onComposerKey(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void send(input);
    }
  }

  const active = DESKS.find((item) => item.id === desk) ?? DESKS[0];
  const ActiveIcon = active.icon;
  const liveState =
    desk === "assistant"
      ? { tone: "success" as const, label: "Live data" }
      : deskQ.isError
        ? { tone: "warning" as const, label: "Unavailable" }
        : deskQ.isLoading
          ? { tone: "neutral" as const, label: "Loading" }
          : { tone: "success" as const, label: "Live" };

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
                <Badge tone={liveState.tone}>{liveState.label}</Badge>
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
                    <div key={`a-${index}`} className="mr-auto w-full max-w-[min(100%,46rem)]">
                      <div
                        className={cn(
                          "rounded-2xl border px-4 py-3 text-[var(--fg)]",
                          message.error
                            ? "border-[color-mix(in_srgb,var(--warning)_45%,var(--border))] bg-[var(--surface-2)]"
                            : "border-[var(--border)] bg-[var(--surface-2)]",
                        )}
                      >
                        {message.live && !message.error && message.startedAt ? (
                          <AnalysisTrace
                            stages={message.stages ?? []}
                            thinking={message.thinking ?? ""}
                            startedAt={message.startedAt}
                            endedAt={message.endedAt}
                            answering={Boolean(message.content)}
                            finished={!message.streaming}
                          />
                        ) : null}
                        {message.content ? (
                          <TypewriterMarkdown
                            text={message.content}
                            animate={Boolean(message.live) && !message.typed}
                            onCaughtUp={() => {
                              if (!message.streaming && !message.typed && message.live) {
                                setMessages((cur) =>
                                  cur.map((m, j) => (j === index ? { ...m, typed: true } : m)),
                                );
                              }
                            }}
                          />
                        ) : !message.live || message.error ? (
                          <ThinkingDots hasImage={Boolean(messages[index - 1]?.images?.length)} />
                        ) : null}
                      </div>
                      {!message.error && !message.streaming && (message.typed || !message.live) ? (
                        <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 px-1 text-[11px] text-[var(--fg-subtle)]">
                          {message.meta?.as_of_utc ? (
                            <span>
                              Live data {formatUtcTime(String(message.meta.as_of_utc))}
                              {typeof message.meta.bid === "number" && typeof message.meta.ask === "number"
                                ? ` · XAUUSD ${formatPrice((message.meta.bid + message.meta.ask) / 2)}`
                                : ""}
                            </span>
                          ) : null}
                          <span>QuantForg AI</span>
                          {!message.streaming && message.content ? (
                            <button
                              type="button"
                              className="inline-flex items-center gap-1 hover:text-[var(--fg)]"
                              onClick={() => void copyAnswer(index, message.content)}
                            >
                              {copied === index ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                              {copied === index ? "Copied" : "Copy"}
                            </button>
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                  ),
                )}
              </div>
            )
          ) : null}

          {desk === "insights" ? <InsightsDesk onAsk={askFromDesk} /> : null}
          {desk === "analysis" ? <AnalysisDesk onAsk={askFromDesk} /> : null}
          {desk === "strategy" ? <StrategyDesk onAsk={askFromDesk} /> : null}
          {desk === "news" ? <NewsDesk onAsk={askFromDesk} /> : null}
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
              {busy ? (
                <Button
                  type="button"
                  variant="secondary"
                  className="h-11 w-11 shrink-0 px-0"
                  aria-label="Stop answer"
                  onClick={() => abortRef.current?.abort()}
                >
                  <Square className="h-3.5 w-3.5" fill="currentColor" />
                </Button>
              ) : (
                <Button
                  type="submit"
                  className="h-11 w-11 shrink-0 px-0"
                  aria-label="Send message"
                  disabled={input.trim() === "" && attachments.length === 0}
                >
                  <Send className="h-4 w-4" />
                </Button>
              )}
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

function ThinkingDots({ hasImage }: { hasImage: boolean }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm text-[var(--fg-muted)]">
      <span className="inline-flex gap-1" aria-hidden>
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[var(--accent)] [animation-delay:-0.3s]" />
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[var(--accent)] [animation-delay:-0.15s]" />
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[var(--accent)]" />
      </span>
      {hasImage ? "Reading your chart and the live market…" : "Reading the live market…"}
    </span>
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
