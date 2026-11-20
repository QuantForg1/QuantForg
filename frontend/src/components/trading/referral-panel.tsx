"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Check, Copy, Gift } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { DeskQueryState } from "@/components/desk/query-state";
import { ApiError, apiFetch } from "@/lib/api/client";

type Reward = {
  event_id?: string;
  reward_status?: string;
  reward_days?: number | null;
  created_at?: string | null;
  applied_at?: string | null;
};

type ReferralSummary = {
  available?: boolean;
  code?: string | null;
  link_path?: string | null;
  history?: { status?: string; code?: string }[];
  rewards?: Reward[];
  reward_days_applied?: number;
  reward_days_pending?: number;
};

const REASONS: Record<string, string> = {
  attributed: "Done. The person who invited you will be rewarded when you subscribe.",
  self_referral: "You can't use your own code.",
  duplicate_attribution: "This account is already linked to a referral.",
  existing_customer: "Referral codes apply to new customers before their first payment.",
  invalid_referral: "That code doesn't exist. Check it and try again.",
  rate_limited: "Too many attempts. Try again in an hour.",
};

function formatDate(iso?: string | null) {
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? ""
    : d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export function ReferralPanel() {
  const summary = useQuery({
    queryKey: ["referrals"],
    queryFn: () => apiFetch<ReferralSummary>("/referrals/me"),
    retry: false,
  });
  const [code, setCode] = useState("");
  const [result, setResult] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const disabled = summary.error instanceof ApiError && summary.error.status === 404;
  const data = summary.data;
  const link =
    data?.link_path && typeof window !== "undefined"
      ? `${window.location.origin}${data.link_path}`
      : (data?.link_path ?? null);
  const invited = data?.history?.length ?? 0;
  const applied = data?.reward_days_applied ?? 0;
  const pending = data?.reward_days_pending ?? 0;

  return (
    <div className="qf-desk min-w-0 space-y-5 overflow-x-hidden">
      <PageHeader
        eyebrow="Account"
        title="Invite friends, get a free month"
        description="Share your link. When a friend you invited makes their first payment, you get 30 extra days on your subscription."
      />
      <DeskQueryState
        isLoading={summary.isLoading}
        isError={summary.isError && !disabled}
        errorMessage="Your referral details could not be loaded."
        onRetry={() => void summary.refetch()}
        isEmpty={disabled || data?.available === false}
        empty={{
          icon: Gift,
          title: disabled ? "Referrals are not available yet" : "Referral details are unavailable",
          description: "Please try again later.",
        }}
      >
        <section className="rounded-xl border border-[var(--border)] p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">Your invite link</p>
          <div className="mt-2 flex flex-col gap-2 sm:flex-row sm:items-center">
            <code className="min-w-0 flex-1 truncate rounded-md bg-[var(--surface-2)] px-3 py-2 text-sm">
              {link ?? "Unavailable"}
            </code>
            <button
              type="button"
              disabled={!link}
              onClick={() => {
                if (!link) return;
                void navigator.clipboard?.writeText(link).then(() => {
                  setCopied(true);
                  window.setTimeout(() => setCopied(false), 2000);
                });
              }}
              className="inline-flex h-9 items-center justify-center gap-1.5 rounded-md bg-[var(--accent)] px-4 text-sm font-semibold text-[var(--accent-fg)] disabled:opacity-50"
            >
              {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
              {copied ? "Copied" : "Copy link"}
            </button>
          </div>
          <p className="mt-2 text-xs text-[var(--fg-muted)]">
            Code: <span className="font-mono">{data?.code ?? "—"}</span>
          </p>
        </section>

        <section className="grid gap-3 sm:grid-cols-3">
          {(
            [
              ["Friends who joined", String(invited)],
              ["Free days added", `${applied}`],
              ["Free days waiting", `${pending}`],
            ] as const
          ).map(([label, value]) => (
            <div key={label} className="rounded-xl border border-[var(--border)] p-4">
              <p className="text-xs text-[var(--fg-muted)]">{label}</p>
              <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
            </div>
          ))}
        </section>
        {pending > 0 ? (
          <p className="text-xs text-[var(--fg-muted)]">
            Waiting days are added automatically when your own subscription is active (at your next payment).
          </p>
        ) : null}

        <section className="rounded-xl border border-[var(--border)] p-4">
          <h2 className="text-sm font-semibold">Rewards</h2>
          {data?.rewards?.length ? (
            <ul className="mt-2 divide-y divide-[var(--border)] text-sm">
              {data.rewards.map((item, i) => (
                <li key={item.event_id ?? i} className="flex items-center justify-between gap-2 py-2">
                  <span>+{item.reward_days ?? 30} days · friend subscribed {formatDate(item.created_at)}</span>
                  <span
                    className={
                      item.reward_status === "applied" ? "text-[var(--success)]" : "text-[var(--warning)]"
                    }
                  >
                    {item.reward_status === "applied" ? `Added ${formatDate(item.applied_at)}` : "Waiting"}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-[var(--fg-muted)]">
              No rewards yet. They appear here when a friend you invited subscribes.
            </p>
          )}
        </section>

        <section className="rounded-xl border border-[var(--border)] p-4">
          <h2 className="text-sm font-semibold">Were you invited by someone?</h2>
          <p className="mt-1 text-xs text-[var(--fg-muted)]">
            Enter their code before your first payment so they get rewarded.
          </p>
          <form
            className="mt-3 flex flex-col gap-2 sm:flex-row"
            onSubmit={(event) => {
              event.preventDefault();
              void apiFetch<Record<string, unknown>>("/referrals/attribute", {
                method: "POST",
                body: { code },
              })
                .then((response) => {
                  const key = response.status === "attributed" ? "attributed" : String(response.reason ?? "");
                  setResult(REASONS[key] ?? "The code was not accepted.");
                  void summary.refetch();
                })
                .catch(() => setResult("The code could not be checked. Try again."));
            }}
          >
            <input
              value={code}
              onChange={(event) => setCode(event.target.value.toUpperCase())}
              aria-label="Invite code"
              placeholder="Invite code"
              maxLength={32}
              className="min-w-0 flex-1 rounded-md border border-[var(--border)] bg-transparent px-3 py-2 text-sm"
            />
            <button
              type="submit"
              disabled={!code.trim()}
              className="rounded-md border border-[var(--border)] px-4 py-2 text-sm font-medium disabled:opacity-50"
            >
              Apply code
            </button>
          </form>
          {result ? <p className="mt-2 text-sm">{result}</p> : null}
        </section>
        <p className="text-[11px] text-[var(--fg-subtle)]">
          Rewards are subscription days, not cash. One reward per invited customer. Self-referrals and codes added
          after a first payment don&apos;t count.
        </p>
      </DeskQueryState>
    </div>
  );
}
