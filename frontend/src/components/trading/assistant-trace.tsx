"use client";

import { useEffect, useRef, useState } from "react";
import { Brain, Check, ChevronDown, Loader2 } from "lucide-react";
import { AssistantMarkdown } from "@/components/trading/assistant-message";
import { revealRate, revealTo } from "@/lib/assistant/stages";
import type { AssistantStage } from "@/lib/assistant/stream";
import { cn } from "@/lib/utils";

const STAGE_REVEAL_MS = 320;

/** Elapsed seconds since `startedAt`, ticking while `running`. */
function useElapsed(startedAt: number, running: boolean, endedAt?: number): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!running) return;
    const t = window.setInterval(() => setNow(Date.now()), 250);
    return () => window.clearInterval(t);
  }, [running]);
  return Math.max(0, Math.round(((endedAt ?? now) - startedAt) / 1000));
}

/**
 * Live analysis trace: the real steps the server reports (price, trend,
 * levels, news, chart), the model's reasoning summary while it thinks, then
 * collapses to a one-line summary once the answer starts.
 */
export function AnalysisTrace({
  stages,
  thinking,
  startedAt,
  answering,
  finished,
  endedAt,
}: {
  stages: AssistantStage[];
  thinking: string;
  startedAt: number;
  answering: boolean;
  finished: boolean;
  endedAt?: number;
}) {
  const [open, setOpen] = useState(true);
  const userToggled = useRef(false);
  const [revealed, setRevealed] = useState(0);
  const elapsed = useElapsed(startedAt, !answering && !finished, endedAt);

  // Reveal steps one after another so each is readable.
  useEffect(() => {
    if (revealed >= stages.length) return;
    const t = window.setTimeout(() => setRevealed((n) => n + 1), revealed === 0 ? 0 : STAGE_REVEAL_MS);
    return () => window.clearTimeout(t);
  }, [revealed, stages.length]);

  // Collapse automatically when the answer starts (unless the user chose).
  useEffect(() => {
    if (answering && !userToggled.current) setOpen(false);
  }, [answering]);

  const working = !answering && !finished;
  const visible = stages.slice(0, Math.max(revealed, working ? 0 : stages.length));
  const doneCount = stages.filter((s) => s.status === "done").length;

  return (
    <div className="mb-3 rounded-xl border border-[color-mix(in_srgb,var(--accent)_22%,var(--border))] bg-[color-mix(in_srgb,var(--accent)_5%,transparent)]">
      <button
        type="button"
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs font-medium text-[var(--fg-muted)]"
        aria-expanded={open}
        onClick={() => {
          userToggled.current = true;
          setOpen((v) => !v);
        }}
      >
        {working ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin text-[var(--accent)]" />
        ) : (
          <Brain className="h-3.5 w-3.5 text-[var(--accent)]" />
        )}
        <span className={cn(working && "qf-shimmer-text")}>
          {working
            ? `Analyzing the market · ${elapsed}s`
            : `Analyzed ${doneCount} data source${doneCount === 1 ? "" : "s"} · thought for ${elapsed}s`}
        </span>
        <ChevronDown className={cn("ml-auto h-3.5 w-3.5 transition-transform", open && "rotate-180")} />
      </button>
      {open ? (
        <div className="space-y-2 px-3 pb-3">
          <ol className="space-y-1.5">
            {visible.map((s) => (
              <li
                key={s.key}
                className="qf-step-in flex items-start gap-2 text-xs"
              >
                <span className="mt-0.5 grid h-4 w-4 shrink-0 place-items-center">
                  {s.status === "done" ? (
                    <Check className="h-3.5 w-3.5 text-[var(--success)]" />
                  ) : (
                    <Loader2 className="h-3.5 w-3.5 animate-spin text-[var(--accent)]" />
                  )}
                </span>
                <span className="min-w-0">
                  <span className={cn("font-medium", s.status === "done" ? "text-[var(--fg)]" : "text-[var(--accent)]")}>
                    {s.label}
                  </span>
                  {s.detail ? <span className="block text-[var(--fg-muted)]">{s.detail}</span> : null}
                </span>
              </li>
            ))}
          </ol>
          {thinking.trim() ? (
            <div className="border-l-2 border-[color-mix(in_srgb,var(--accent)_40%,var(--border))] pl-3 text-xs italic leading-relaxed text-[var(--fg-muted)]">
              <TypewriterText text={thinking.trim()} animate={working} />
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

/** Reveal `text` at a steady, readable pace, word by word. */
function useTypewriter(text: string, animate: boolean): string {
  const [shown, setShown] = useState(0);
  const target = useRef(text);
  useEffect(() => {
    target.current = text;
  }, [text]);
  useEffect(() => {
    if (!animate) return;
    let raf = 0;
    let last = performance.now();
    let budget = 0;
    const tick = (now: number) => {
      const dt = Math.min(0.1, (now - last) / 1000);
      last = now;
      setShown((n) => {
        const full = target.current;
        const remaining = full.length - n;
        if (remaining <= 0) return n;
        budget += revealRate(remaining) * dt;
        if (budget < 1) return n;
        const next = revealTo(full, n, budget);
        budget -= next - n;
        if (budget < 0) budget = 0;
        return next;
      });
      raf = window.requestAnimationFrame(tick);
    };
    raf = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(raf);
  }, [animate]);
  return animate ? text.slice(0, Math.min(shown, text.length)) : text;
}

function TypewriterText({ text, animate }: { text: string; animate: boolean }) {
  const shown = useTypewriter(text, animate);
  return <AssistantMarkdown text={shown} compact />;
}

/**
 * Markdown answer that types itself out. `animate` stays true for answers
 * produced in this session; history renders instantly.
 */
export function TypewriterMarkdown({
  text,
  animate,
  onCaughtUp,
}: {
  text: string;
  animate: boolean;
  onCaughtUp?: () => void;
}) {
  const shown = useTypewriter(text, animate);
  const caughtUp = shown.length >= text.length;
  // Parent decides whether to act (it ignores calls while still streaming).
  useEffect(() => {
    if (caughtUp && text.length > 0) onCaughtUp?.();
  });
  return (
    <div className="relative">
      <AssistantMarkdown text={shown} />
      {animate && !caughtUp ? (
        <span
          className="ml-0.5 inline-block h-4 w-[3px] translate-y-0.5 animate-pulse rounded-sm bg-[var(--accent)]"
          aria-hidden
        />
      ) : null}
    </div>
  );
}
