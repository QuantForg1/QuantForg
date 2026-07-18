"use client";

import { memo } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { cn, formatNumber } from "@/lib/utils";
import type { CounselRecommendation } from "@/components/counsel/recommendation-model";
import { CounselEmpty } from "@/components/counsel/empty-state";

/**
 * Recommendation Card — Action, Reason, Evidence, Confidence, Impact, Approval.
 * Never places orders; Terminal is the only execution surface.
 */
export const RecommendationCard = memo(function RecommendationCard({
  recommendation,
  focused,
  className,
}: {
  recommendation: CounselRecommendation | null;
  focused?: boolean;
  className?: string;
}) {
  if (!recommendation) {
    return (
      <section
        className={cn(
          "flex h-full min-h-0 flex-col rounded-md border border-[var(--border)] bg-[var(--surface)] p-3",
          focused && "ring-1 ring-[var(--accent)]",
          className,
        )}
        aria-label="Recommendation"
      >
        <h2 className="qf-label mb-2 text-[var(--fg)]">Recommendation</h2>
        <CounselEmpty
          title="No recommendation"
          description="Counsel will not invent trade ideas. Evaluate when ready."
        />
      </section>
    );
  }

  const isWait = recommendation.action === "WAIT";

  return (
    <section
      className={cn(
        "flex h-full min-h-0 flex-col rounded-md border border-[var(--border)] bg-[var(--surface)] p-3",
        focused && "ring-1 ring-[var(--accent)]",
        className,
      )}
      aria-label="Recommendation"
    >
      <header className="mb-2 flex shrink-0 items-center justify-between gap-2">
        <h2 className="qf-label text-[var(--fg)]">Recommendation</h2>
        <Button size="sm" variant="secondary" className="h-7 text-[11px]" asChild>
          <Link
            href={`/terminal?symbol=${encodeURIComponent(recommendation.symbol)}`}
          >
            Open Terminal
          </Link>
        </Button>
      </header>

      <dl className="min-h-0 flex-1 space-y-2 overflow-y-auto text-[11px]">
        <Field label="Action">
          <span
            className={cn(
              "font-mono font-semibold",
              isWait ? "text-[var(--warning)]" : "text-[var(--accent)]",
            )}
          >
            {recommendation.action}
          </span>
        </Field>
        <Field label="Reason">{recommendation.reason || "—"}</Field>
        <Field label="Evidence">
          {recommendation.evidence.length === 0 ? (
            <span className="text-[var(--fg-subtle)]">No evidence fields in payload</span>
          ) : (
            <ul className="list-inside list-disc space-y-0.5 text-[var(--fg-muted)]">
              {recommendation.evidence.map((e) => (
                <li key={e.slice(0, 40)}>{e}</li>
              ))}
            </ul>
          )}
        </Field>
        <Field label="Confidence">
          {recommendation.confidence == null
            ? "—"
            : `${formatNumber(recommendation.confidence, 0)}%`}
        </Field>
        <Field label="Impact">{recommendation.impact}</Field>
        <Field label="Approval">
          <span className="capitalize">{recommendation.approval.replace(/_/g, " ")}</span>
        </Field>
        {!isWait ? (
          <div className="grid grid-cols-2 gap-2 border-t border-[var(--border)] pt-2 sm:grid-cols-4">
            <Mini label="Lots" value={recommendation.lotSize} />
            <Mini label="SL" value={recommendation.sl} />
            <Mini label="TP" value={recommendation.tp} />
            <Mini label="R:R" value={recommendation.rr} />
          </div>
        ) : null}
        <p className="qf-caption pt-1">
          Advisory only. Execution happens exclusively in Terminal after human approval.
        </p>
      </dl>
    </section>
  );
});

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <dt className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
        {label}
      </dt>
      <dd className="mt-0.5 text-[var(--fg)]">{children}</dd>
    </div>
  );
}

function Mini({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[10px] text-[var(--fg-subtle)]">{label}</p>
      <p className="font-mono tabular text-[var(--fg)]">{value}</p>
    </div>
  );
}
