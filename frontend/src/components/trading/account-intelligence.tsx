"use client";

import type { ReactNode } from "react";
import { useQuery, useQueries } from "@tanstack/react-query";
import { HeartPulse } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { DeskQueryState } from "@/components/desk/query-state";
import { ApiError, apiFetch } from "@/lib/api/client";
import {
  COACH_QUESTIONS,
  RELIABILITY_COMPONENTS,
  coachAnswerText,
  figureText,
  reliabilityLabel,
} from "@/lib/intelligence/account-reports";
import { formatZonedDateTime, localeSupport } from "@/lib/i18n/presentation";

function disabled(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404;
}

export function AccountIntelligence() {
  const observation = useQuery({
    queryKey: ["market-observation", "XAUUSD"],
    queryFn: () => apiFetch<Record<string, unknown>>("/market-observation/XAUUSD"),
    retry: false,
  });
  const explanations = useQuery({
    queryKey: ["trade-explanations"],
    queryFn: () => apiFetch<Record<string, unknown>>("/trade-explanations"),
    retry: false,
  });
  const risk = useQuery({
    queryKey: ["risk-intelligence"],
    queryFn: () => apiFetch<Record<string, unknown>>("/risk-intelligence/insight"),
    retry: false,
  });
  const reliability = useQuery({
    queryKey: ["reliability-center"],
    queryFn: () => apiFetch<Record<string, unknown>>("/reliability/status"),
    retry: false,
  });
  const coach = useQueries({
    queries: COACH_QUESTIONS.map((question) => ({
      queryKey: ["trading-coach", question.id],
      queryFn: () =>
        apiFetch<Record<string, unknown>>(
          `/trading-coach/answer?question_id=${encodeURIComponent(question.id)}`,
        ),
      retry: false,
    })),
  });
  const language = localeSupport(
    typeof navigator === "undefined" ? "en-US" : navigator.language,
  );

  return (
    <div className="qf-desk min-w-0 space-y-5 overflow-x-hidden">
      <PageHeader
        eyebrow="Intelligence"
        title="Account intelligence"
        description="Read-only reports for this signed-in account. Missing records stay unavailable. This page does not change risk limits or send an order."
      />
      <Section
        title="Market observation"
        note="Current XAUUSD observation only. It does not replace missing historical evidence."
        query={observation}
        disabledTitle="Market observation is not enabled"
      >
        <Fact label="Symbol" value={figureText(observation.data?.symbol)} />
        <Fact label="Freshness" value={figureText(observation.data?.freshness)} />
        <Fact label="Spread" value={figureText(observation.data?.spread)} />
        <Fact label="Trend" value={figureText(observation.data?.trend)} />
        <Fact label="Read" value={when(observation.data?.read_at)} />
      </Section>
      <Section
        title="Trade explanations"
        note="ORDER_SENT is not FILLED. NOT_REACHED is not a pass."
        query={explanations}
        disabledTitle="Trade explanations are not enabled"
      >
        <ExplanationList payload={explanations.data} />
      </Section>
      <Section
        title="Risk"
        note="Shown from the account snapshot. The risk profile is not changed."
        query={risk}
        disabledTitle="Risk intelligence is not enabled"
      >
        <Fact label="Equity" value={figureText(risk.data?.equity)} />
        <Fact label="Balance" value={figureText(risk.data?.balance)} />
        <Fact label="Floating result" value={figureText(risk.data?.floating_pnl)} />
        <Fact label="Margin used" value={figureText(risk.data?.margin_used_pct)} />
        <p className="text-xs text-[var(--text-secondary)]">
          Account currency is shown only when the report states it. No conversion is applied.
        </p>
      </Section>
      <Section
        title="Reliability"
        note="A dependency is healthy only when this response includes that check."
        query={reliability}
        disabledTitle="Reliability center is not enabled"
      >
        <ul className="space-y-1 text-sm">
          {RELIABILITY_COMPONENTS.map((name) => (
            <li key={name} className="flex flex-wrap justify-between gap-2">
              <span>{name}</span>
              <span className="text-[var(--text-secondary)]">
                {reliabilityLabel(reliability.data, name)}
              </span>
            </li>
          ))}
        </ul>
      </Section>
      <section className="rounded-md border border-[var(--border)] p-4">
        <h2 className="text-sm font-medium">Trading coach</h2>
        <p className="mt-2 text-sm text-[var(--text-secondary)]">
          Answers come from stored records for this account. A missing record stays unavailable.
        </p>
        <ul className="mt-3 space-y-2">
          {COACH_QUESTIONS.map((question, index) => {
            const item = coach[index];
            const text = disabled(item?.error)
              ? "Not enabled"
              : item?.isError
                ? "Could not be loaded"
                : coachAnswerText(item?.data);
            return (
              <li key={question.id} className="flex flex-wrap justify-between gap-2 text-sm">
                <span>{question.label}</span>
                <span className="text-[var(--text-secondary)]">{item?.isLoading ? "Loading" : text}</span>
              </li>
            );
          })}
        </ul>
      </section>
      <p className="text-xs text-[var(--text-secondary)]">
        {language.supported
          ? "The verified interface language is English (United States)."
          : "This browser language is not a verified QuantForg language. The page stays in English."}
        {" "}Dates below are UTC.
      </p>
    </div>
  );
}

function when(value: unknown): string {
  return typeof value === "string" ? formatZonedDateTime(value, "UTC") : "Unavailable";
}

function Section({
  title,
  note,
  query,
  disabledTitle,
  children,
}: {
  title: string;
  note: string;
  query: { isLoading: boolean; isError: boolean; error: unknown; refetch: () => unknown; data?: unknown };
  disabledTitle: string;
  children: ReactNode;
}) {
  const hidden = disabled(query.error);
  return (
    <section className="rounded-md border border-[var(--border)] p-4">
      <h2 className="text-sm font-medium">{title}</h2>
      <p className="mt-2 text-sm text-[var(--text-secondary)]">{note}</p>
      <div className="mt-3">
        <DeskQueryState
          isLoading={query.isLoading}
          isError={query.isError && !hidden}
          errorMessage="This report could not be loaded."
          onRetry={() => void query.refetch()}
          isEmpty={hidden}
          empty={{
            icon: HeartPulse,
            title: disabledTitle,
            description: "The report stays hidden until that service is enabled for this environment.",
          }}
        >
          <div className="space-y-2">{children}</div>
        </DeskQueryState>
      </div>
    </section>
  );
}

function ExplanationList({ payload }: { payload: Record<string, unknown> | undefined }) {
  const rows = Array.isArray(payload?.explanations) ? payload.explanations : [];
  if (rows.length === 0) {
    return (
      <p className="text-sm text-[var(--text-secondary)]">
        {figureText(payload?.reason) === "Unavailable"
          ? "No explanation record was returned."
          : figureText(payload?.reason)}
      </p>
    );
  }
  return (
    <ul className="space-y-2 text-sm">
      {rows.slice(0, 20).map((row, index) => (
        <li key={index} className="break-words">
          {figureText(row)}
        </li>
      ))}
    </ul>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-wrap justify-between gap-2 text-sm">
      <dt>{label}</dt>
      <dd className="min-w-0 break-words text-[var(--text-secondary)]">{value}</dd>
    </div>
  );
}
