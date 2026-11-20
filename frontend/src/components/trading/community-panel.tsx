"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Flag, MessageSquare, MessageSquareWarning, ShieldCheck, Trash2, UserX } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { DeskQueryState } from "@/components/desk/query-state";
import { ApiError, apiFetch } from "@/lib/api/client";

type Comment = {
  comment_id: string;
  author_id: string;
  body: string;
  created_at?: string | null;
  mine?: boolean;
  can_delete?: boolean;
};

type Post = {
  post_id: string;
  author_id: string;
  body: string;
  visibility: string;
  created_at?: string | null;
  mine?: boolean;
  can_delete?: boolean;
  comments?: Comment[];
};

type Feed = { available?: boolean; is_moderator?: boolean; posts?: Post[] };

type Report = {
  report_id: string;
  target_type: string;
  reason: string;
  content?: string | null;
  reports_on_target?: number;
};

function who(id: string, mine?: boolean) {
  return mine ? "You" : `Member ${id.slice(0, 6).toUpperCase()}`;
}

function when(iso?: string | null) {
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? ""
    : d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

const REJECTIONS: Record<string, string> = {
  rate_limited: "You're posting too fast. Please wait a little.",
  invalid_post: "Posts must be 1 to 2,000 characters.",
  invalid_comment: "Comments must be 1 to 1,000 characters.",
  forbidden: "You can't change this.",
  not_found: "This post is no longer available.",
};

function answer(r: Record<string, unknown>, ok: string) {
  return r.status === "rejected" ? (REJECTIONS[String(r.reason)] ?? "That didn't work.") : ok;
}

function ModerationQueue() {
  const q = useQuery({
    queryKey: ["community-moderation"],
    queryFn: () => apiFetch<{ reports?: Report[] }>("/community/moderation/reports"),
    retry: false,
    refetchInterval: 60_000,
  });
  if (q.error instanceof ApiError && q.error.status === 403) return null;
  if (!q.data) return null;
  const reports = q.data.reports ?? [];
  const decide = (id: string, action: "remove" | "dismiss") =>
    void apiFetch(`/community/moderation/reports/${id}`, { method: "POST", body: { action } }).then(() =>
      q.refetch(),
    );
  return (
    <section className="rounded-xl border border-[color-mix(in_srgb,var(--warning)_45%,var(--border))] p-4">
      <h2 className="flex items-center gap-2 text-sm font-semibold">
        <ShieldCheck className="h-4 w-4 text-[var(--warning)]" /> Moderation queue ({reports.length})
      </h2>
      {reports.length === 0 ? (
        <p className="mt-2 text-sm text-[var(--fg-muted)]">No open reports.</p>
      ) : (
        <ul className="mt-3 space-y-3">
          {reports.map((r) => (
            <li key={r.report_id} className="rounded-lg bg-[var(--surface-2)] p-3 text-sm">
              <p className="text-xs text-[var(--fg-muted)]">
                Reported {r.target_type} · {r.reports_on_target ?? 1} report(s) · reason: {r.reason}
              </p>
              <p className="mt-1 break-words">{r.content ?? "(content already removed)"}</p>
              <div className="mt-2 flex gap-2">
                <button
                  type="button"
                  onClick={() => decide(r.report_id, "remove")}
                  className="rounded-md bg-[var(--danger)] px-3 py-1.5 text-xs font-semibold text-white"
                >
                  Remove content
                </button>
                <button
                  type="button"
                  onClick={() => decide(r.report_id, "dismiss")}
                  className="rounded-md border border-[var(--border)] px-3 py-1.5 text-xs"
                >
                  Dismiss
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function CommunityPanel() {
  const posts = useQuery({
    queryKey: ["community-posts"],
    queryFn: () => apiFetch<Feed>("/community/posts"),
    retry: false,
  });
  const [body, setBody] = useState("");
  const [visibility, setVisibility] = useState("public");
  const [notice, setNotice] = useState("");
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const disabled = posts.error instanceof ApiError && posts.error.status === 404;
  const refresh = () => void posts.refetch();
  const act = (path: string, init: { method: string; body?: unknown }, ok: string) =>
    void apiFetch<Record<string, unknown>>(path, init)
      .then((r) => {
        setNotice(answer(r, ok));
        refresh();
      })
      .catch(() => setNotice("That didn't work. Try again."));

  return (
    <div className="qf-desk min-w-0 space-y-5 overflow-x-hidden">
      <PageHeader
        eyebrow="Account"
        title="Community"
        description="Talk gold trading with other QuantForg members. Be respectful: no spam, no promotions, no promises of profit."
      />
      <DeskQueryState
        isLoading={posts.isLoading}
        isError={posts.isError && !disabled}
        errorMessage="The community feed could not be loaded."
        onRetry={refresh}
        isEmpty={disabled || posts.data?.available === false}
        empty={{
          icon: MessageSquareWarning,
          title: disabled ? "Community is not available yet" : "The community is unavailable right now",
          description: "Please try again later.",
        }}
      >
        <ModerationQueue />
        <form
          className="space-y-2 rounded-xl border border-[var(--border)] p-4"
          onSubmit={(event) => {
            event.preventDefault();
            act("/community/posts", { method: "POST", body: { body, visibility } }, "Posted.");
            setBody("");
          }}
        >
          <textarea
            value={body}
            onChange={(event) => setBody(event.target.value)}
            aria-label="New post"
            placeholder="Share an idea, a question or a lesson from your trading…"
            maxLength={2000}
            className="min-h-24 w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-2 text-sm"
          />
          <div className="flex flex-wrap items-center justify-between gap-2">
            <label className="text-xs text-[var(--fg-muted)]">
              Who can see it
              <select
                value={visibility}
                onChange={(event) => setVisibility(event.target.value)}
                className="ml-2 rounded-md border border-[var(--border)] bg-transparent px-2 py-1 text-sm"
              >
                <option value="public">Everyone in the community</option>
                <option value="private">Only me</option>
              </select>
            </label>
            <button
              type="submit"
              disabled={!body.trim()}
              className="rounded-md bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-[var(--accent-fg)] disabled:opacity-50"
            >
              Post
            </button>
          </div>
        </form>
        {notice ? (
          <p className="text-sm" role="status">
            {notice}
          </p>
        ) : null}

        <ul className="space-y-3">
          {(posts.data?.posts ?? []).map((post) => (
            <li key={post.post_id} className="rounded-xl border border-[var(--border)] p-4 text-sm">
              <div className="flex items-center justify-between gap-2 text-xs text-[var(--fg-muted)]">
                <span>
                  {who(post.author_id, post.mine)} · {when(post.created_at)}
                  {post.visibility === "private" ? " · only you" : ""}
                </span>
                <span className="flex gap-3">
                  {!post.mine ? (
                    <>
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 hover:text-[var(--fg)]"
                        onClick={() => {
                          const reason = window.prompt("Why are you reporting this post?");
                          if (reason?.trim())
                            act(
                              "/community/reports",
                              { method: "POST", body: { target_type: "post", target_id: post.post_id, reason } },
                              "Thanks. A moderator will review it.",
                            );
                        }}
                      >
                        <Flag className="h-3.5 w-3.5" /> Report
                      </button>
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 hover:text-[var(--fg)]"
                        onClick={() =>
                          act(
                            "/community/blocks",
                            { method: "POST", body: { user_id: post.author_id } },
                            "Blocked. You won't see this member any more.",
                          )
                        }
                      >
                        <UserX className="h-3.5 w-3.5" /> Block
                      </button>
                    </>
                  ) : null}
                  {post.can_delete ? (
                    <button
                      type="button"
                      className="inline-flex items-center gap-1 hover:text-[var(--danger)]"
                      onClick={() => {
                        if (window.confirm("Delete this post?"))
                          act(`/community/posts/${post.post_id}`, { method: "DELETE" }, "Post deleted.");
                      }}
                    >
                      <Trash2 className="h-3.5 w-3.5" /> Delete
                    </button>
                  ) : null}
                </span>
              </div>
              <p className="mt-2 whitespace-pre-wrap break-words">{post.body}</p>

              <div className="mt-3 space-y-2 border-t border-[var(--border)] pt-3">
                {(post.comments ?? []).map((c) => (
                  <div key={c.comment_id} className="flex items-start justify-between gap-2 text-xs">
                    <p className="min-w-0 break-words">
                      <span className="font-semibold">{who(c.author_id, c.mine)}:</span> {c.body}
                    </p>
                    <span className="flex shrink-0 gap-2 text-[var(--fg-muted)]">
                      {!c.mine ? (
                        <button
                          type="button"
                          aria-label="Report comment"
                          onClick={() => {
                            const reason = window.prompt("Why are you reporting this comment?");
                            if (reason?.trim())
                              act(
                                "/community/reports",
                                {
                                  method: "POST",
                                  body: { target_type: "comment", target_id: c.comment_id, reason },
                                },
                                "Thanks. A moderator will review it.",
                              );
                          }}
                        >
                          <Flag className="h-3.5 w-3.5" />
                        </button>
                      ) : null}
                      {c.can_delete ? (
                        <button
                          type="button"
                          aria-label="Delete comment"
                          onClick={() => act(`/community/comments/${c.comment_id}`, { method: "DELETE" }, "Comment deleted.")}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      ) : null}
                    </span>
                  </div>
                ))}
                <form
                  className="flex gap-2"
                  onSubmit={(event) => {
                    event.preventDefault();
                    const text = drafts[post.post_id] ?? "";
                    if (!text.trim()) return;
                    act(
                      `/community/posts/${post.post_id}/comments`,
                      { method: "POST", body: { body: text } },
                      "Comment added.",
                    );
                    setDrafts((d) => ({ ...d, [post.post_id]: "" }));
                  }}
                >
                  <input
                    value={drafts[post.post_id] ?? ""}
                    onChange={(e) => setDrafts((d) => ({ ...d, [post.post_id]: e.target.value }))}
                    aria-label="Write a comment"
                    placeholder="Write a comment…"
                    maxLength={1000}
                    className="min-w-0 flex-1 rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-xs"
                  />
                  <button type="submit" className="inline-flex items-center gap-1 rounded-md border border-[var(--border)] px-3 text-xs">
                    <MessageSquare className="h-3.5 w-3.5" /> Reply
                  </button>
                </form>
              </div>
            </li>
          ))}
        </ul>
        {posts.data?.posts?.length === 0 ? (
          <p className="text-sm text-[var(--fg-muted)]">No posts yet. Be the first to start a conversation.</p>
        ) : null}
        <p className="text-[11px] text-[var(--fg-subtle)]">
          Posts are opinions of members, not financial advice. Report anything that breaks the rules.
        </p>
      </DeskQueryState>
    </div>
  );
}
