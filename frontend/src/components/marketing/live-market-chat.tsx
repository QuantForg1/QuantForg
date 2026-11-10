"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MessageCircle, RefreshCw, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { marketChatApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { cn, formatRelativeTime } from "@/lib/utils";
import { useAuthOptional } from "@/providers/auth-provider";

type ChatMessage = {
  id: string;
  display_name: string;
  body: string;
  created_at: string;
  user_id: string;
};

export function LiveMarketChat({
  channel = "xauusd",
  className,
}: {
  channel?: string;
  className?: string;
}) {
  const auth = useAuthOptional();
  const isAuthenticated = auth?.isAuthenticated ?? false;
  const qc = useQueryClient();
  const [draft, setDraft] = useState("");
  const [postError, setPostError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const listQ = useQuery({
    queryKey: ["public-market-chat", channel],
    queryFn: () => marketChatApi.list(channel, 100),
    refetchInterval: 8_000,
    retry: 1,
  });

  const messages = useMemo(() => {
    const rows = asList(asRecord(listQ.data).messages).map(asRecord);
    return rows
      .map((row) => ({
        id: str(row.id),
        display_name: str(row.display_name, "Trader"),
        body: str(row.body),
        created_at: str(row.created_at),
        user_id: str(row.user_id),
      }))
      .filter((m) => m.id && m.body) as ChatMessage[];
  }, [listQ.data]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length]);

  const postMut = useMutation({
    mutationFn: (body: string) => marketChatApi.post({ body, channel }),
    onSuccess: async () => {
      setDraft("");
      setPostError(null);
      await qc.invalidateQueries({ queryKey: ["public-market-chat", channel] });
    },
    onError: (err) => {
      setPostError(err instanceof Error ? err.message : "Could not send message");
    },
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    const body = draft.trim();
    if (!body || postMut.isPending) return;
    postMut.mutate(body);
  }

  return (
    <section
      className={cn(
        "flex h-full min-h-[320px] flex-col overflow-hidden rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--surface)]",
        className,
      )}
      aria-label="Live Market discussion"
    >
      <header className="flex items-center justify-between gap-2 border-b border-[var(--border)] px-3 py-2">
        <div className="flex items-center gap-2">
          <MessageCircle className="h-4 w-4 text-[var(--accent)]" aria-hidden />
          <div>
            <p className="text-sm font-semibold text-[var(--fg)]">Live Market Chat</p>
            <p className="text-[10px] text-[var(--fg-muted)]">
              Public XAUUSD discussion · view without login
            </p>
          </div>
        </div>
        <Button
          size="sm"
          variant="ghost"
          className="h-7 px-2"
          onClick={() => void listQ.refetch()}
          aria-label="Refresh chat"
        >
          <RefreshCw className={cn("h-3.5 w-3.5", listQ.isFetching && "animate-spin")} />
        </Button>
      </header>

      <div className="min-h-0 flex-1 space-y-2 overflow-y-auto px-3 py-3">
        {listQ.isLoading ? (
          <p className="text-xs text-[var(--fg-muted)]">Loading discussion…</p>
        ) : listQ.isError ? (
          <p className="text-xs text-[var(--danger)]" role="alert">
            Discussion temporarily unavailable. Retry shortly.
          </p>
        ) : messages.length === 0 ? (
          <p className="text-xs text-[var(--fg-muted)]">
            No messages yet. Be the first to discuss the gold market.
          </p>
        ) : (
          messages.map((m) => (
            <article
              key={m.id}
              className="rounded-[var(--radius-sm)] border border-[var(--border)]/70 bg-[color-mix(in_srgb,var(--bg)_55%,transparent)] px-2.5 py-2"
            >
              <div className="flex items-baseline justify-between gap-2">
                <p className="truncate text-xs font-semibold text-[var(--fg)]">
                  {m.display_name}
                </p>
                <time className="shrink-0 text-[10px] text-[var(--fg-subtle)]">
                  {m.created_at ? formatRelativeTime(new Date(m.created_at)) : "—"}
                </time>
              </div>
              <p className="mt-1 whitespace-pre-wrap break-words text-sm text-[var(--fg-muted)]">
                {m.body}
              </p>
            </article>
          ))
        )}
        <div ref={bottomRef} />
      </div>

      <footer className="border-t border-[var(--border)] px-3 py-2">
        {isAuthenticated ? (
          <form onSubmit={onSubmit} className="flex gap-2">
            <label className="sr-only" htmlFor="live-market-chat-input">
              Message
            </label>
            <input
              id="live-market-chat-input"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              maxLength={500}
              placeholder="Share a market observation…"
              className="h-9 min-w-0 flex-1 rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--bg)] px-3 text-sm text-[var(--fg)] placeholder:text-[var(--fg-subtle)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
            />
            <Button
              type="submit"
              size="sm"
              className="h-9 px-3"
              disabled={postMut.isPending || !draft.trim()}
            >
              <Send className="h-3.5 w-3.5" />
              Send
            </Button>
          </form>
        ) : (
          <p className="text-xs text-[var(--fg-muted)]">
            Sign in to join the discussion.{" "}
            <Link href="/login?next=/live" className="text-[var(--accent)] underline">
              Sign in
            </Link>{" "}
            or{" "}
            <Link href="/register?next=/live" className="text-[var(--accent)] underline">
              create an account
            </Link>
            .
          </p>
        )}
        {postError ? (
          <p className="mt-1 text-[10px] text-[var(--danger)]" role="alert">
            {postError}
          </p>
        ) : null}
      </footer>
    </section>
  );
}
