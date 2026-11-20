"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Coins } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { DeskQueryState } from "@/components/desk/query-state";
import { ApiError, apiFetch } from "@/lib/api/client";
import { localeSupport, paymentMethodSupport } from "@/lib/i18n/presentation";

type ReferralSummary = {
  available?: boolean;
  code?: string | null;
  link_path?: string | null;
  history?: { status?: string; code?: string }[];
  rewards?: { event_id?: string; reward_amount?: null; reward_status?: string }[];
  reward_balance?: null;
};

export function ReferralPanel() {
  const summary = useQuery({
    queryKey: ["referrals"],
    queryFn: () => apiFetch<ReferralSummary>("/referrals/me"),
    retry: false,
  });
  const [code, setCode] = useState("");
  const [result, setResult] = useState("No attribution submitted.");
  const disabled = summary.error instanceof ApiError && summary.error.status === 404;
  const language = localeSupport(typeof navigator === "undefined" ? "en-US" : navigator.language);
  const link =
    summary.data?.link_path && typeof window !== "undefined"
      ? `${window.location.origin}${summary.data.link_path}`
      : summary.data?.link_path;

  return (
    <div className="qf-desk min-w-0 space-y-5 overflow-x-hidden">
      <PageHeader
        eyebrow="Account"
        title="Referrals"
        description="Codes and attributions only. Reward balances stay unavailable until a payout is recorded."
      />
      <DeskQueryState
        isLoading={summary.isLoading}
        isError={summary.isError && !disabled}
        errorMessage="The referral record could not be loaded."
        onRetry={() => void summary.refetch()}
        isEmpty={disabled || summary.data?.available === false}
        empty={{
          icon: Coins,
          title: disabled ? "Referrals are not enabled" : "Referral records are unavailable",
          description: "No referral balance is shown while the ledger is unavailable.",
        }}
      >
        <section className="rounded-md border border-[var(--border)] p-4 text-sm">
          <p>Code: {summary.data?.code ?? "Unavailable"}</p>
          <p className="mt-2 break-all">Link: {link ?? "Unavailable"}</p>
          <p className="mt-2">Reward balance: Unavailable</p>
          <p className="mt-2 text-[var(--text-secondary)]">
            {language.supported
              ? "Dates use UTC when a timestamp is stored."
              : "This language is not verified. English is shown."}
          </p>
          <p className="text-[var(--text-secondary)]">
            Card payments: {paymentMethodSupport("card")}.
          </p>
        </section>
        <form
          className="flex flex-col gap-2 sm:flex-row"
          onSubmit={(event) => {
            event.preventDefault();
            void apiFetch<Record<string, unknown>>("/referrals/attribute", {
              method: "POST",
              body: { code },
            })
              .then((response) => {
                setResult(
                  response.status === "attributed"
                    ? "Attribution recorded. No reward was issued."
                    : "Attribution was not recorded.",
                );
                void summary.refetch();
              })
              .catch(() => setResult("Attribution was not recorded."));
          }}
        >
          <input
            value={code}
            onChange={(event) => setCode(event.target.value)}
            aria-label="Referral code"
            className="min-w-0 flex-1 rounded-md border border-[var(--border)] bg-transparent px-3 py-2 text-sm"
          />
          <button type="submit" className="rounded-md border border-[var(--border)] px-3 py-2 text-sm">
            Attribute this account
          </button>
        </form>
        <p className="text-sm">{result}</p>
        <section className="rounded-md border border-[var(--border)] p-4">
          <h2 className="text-sm font-medium">History</h2>
          {summary.data?.history?.length ? (
            <ul className="mt-2 space-y-1 text-sm">
              {summary.data.history.map((item, index) => (
                <li key={`${item.code ?? "code"}-${index}`}>Registration attributed</li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-[var(--text-secondary)]">No attributed registrations.</p>
          )}
          <h2 className="mt-4 text-sm font-medium">Rewards</h2>
          {summary.data?.rewards?.length ? (
            <ul className="mt-2 space-y-1 text-sm">
              {summary.data.rewards.map((item) => (
                <li key={item.event_id ?? "event"}>
                  {item.reward_status ?? "not_issued"}. Amount unavailable.
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-[var(--text-secondary)]">No rewards.</p>
          )}
        </section>
      </DeskQueryState>
    </div>
  );
}
