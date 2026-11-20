"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { MessageSquareWarning } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { DeskQueryState } from "@/components/desk/query-state";
import { ApiError, apiFetch } from "@/lib/api/client";
import { formatZonedDateTime } from "@/lib/i18n/presentation";

type Post = {
  post_id: string;
  body: string;
  visibility: string;
  created_at?: string | null;
};

export function CommunityPanel() {
  const posts = useQuery({
    queryKey: ["community-posts"],
    queryFn: () => apiFetch<{ available?: boolean; posts?: Post[] }>("/community/posts"),
    retry: false,
  });
  const [body, setBody] = useState("");
  const [visibility, setVisibility] = useState("private");
  const [notice, setNotice] = useState("");
  const disabled = posts.error instanceof ApiError && posts.error.status === 404;

  return (
    <div className="qf-desk min-w-0 space-y-5 overflow-x-hidden">
      <PageHeader
        eyebrow="Account"
        title="Community"
        description="Posts stay private until you choose public. This page does not create sample customers or engagement."
      />
      <DeskQueryState
        isLoading={posts.isLoading}
        isError={posts.isError && !disabled}
        errorMessage="The community feed could not be loaded."
        onRetry={() => void posts.refetch()}
        isEmpty={disabled || posts.data?.available === false}
        empty={{
          icon: MessageSquareWarning,
          title: disabled ? "Community is not enabled" : "Community records are unavailable",
          description: "No posts are invented while the community store is unavailable.",
        }}
      >
        <form
          className="space-y-2"
          onSubmit={(event) => {
            event.preventDefault();
            void apiFetch("/community/posts", {
              method: "POST",
              body: { body, visibility },
            })
              .then(() => {
                setBody("");
                setNotice("Post submitted.");
                void posts.refetch();
              })
              .catch(() => setNotice("Post was not saved."));
          }}
        >
          <textarea
            value={body}
            onChange={(event) => setBody(event.target.value)}
            aria-label="Post"
            className="min-h-24 w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-2 text-sm"
          />
          <label className="block text-sm">
            Visibility
            <select
              value={visibility}
              onChange={(event) => setVisibility(event.target.value)}
              className="ml-2 rounded-md border border-[var(--border)] bg-transparent px-2 py-1"
            >
              <option value="private">Private</option>
              <option value="public">Public</option>
            </select>
          </label>
          <button type="submit" className="rounded-md border border-[var(--border)] px-3 py-2 text-sm">
            Publish
          </button>
        </form>
        {notice ? <p className="text-sm">{notice}</p> : null}
        <ul className="space-y-3">
          {(posts.data?.posts ?? []).map((post) => (
            <li key={post.post_id} className="rounded-md border border-[var(--border)] p-4 text-sm">
              <p className="break-words">{post.body}</p>
              <p className="mt-2 text-[var(--text-secondary)]">
                {post.visibility}.{" "}
                {post.created_at ? formatZonedDateTime(post.created_at, "UTC") : "Time unavailable"}
              </p>
            </li>
          ))}
        </ul>
        {posts.data?.posts?.length === 0 ? (
          <p className="text-sm text-[var(--text-secondary)]">No posts yet.</p>
        ) : null}
      </DeskQueryState>
    </div>
  );
}
