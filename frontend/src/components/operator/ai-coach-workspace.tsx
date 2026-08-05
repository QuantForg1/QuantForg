"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { GraduationCap } from "lucide-react";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { Badge } from "@/components/ui/badge";
import { ecosystemApi, signalCenterApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";

/**
 * AI Coach — recommendations only. Never executes trades.
 */
export function AiCoachWorkspace() {
  const coachQ = useQuery({
    queryKey: ["ecosystem-coach"],
    queryFn: () => ecosystemApi.coach(),
    staleTime: 30_000,
    refetchInterval: 60_000,
    retry: false,
  });
  const signalsQ = useQuery({
    queryKey: ["signals-center", "ai-coach"],
    queryFn: () => signalCenterApi.list({}),
    staleTime: 30_000,
    refetchInterval: 45_000,
    retry: false,
  });

  const coach = asRecord(coachQ.data);
  const recs = useMemo(() => {
    const fromCoach = asList(
      coach.recommendations || coach.advice || coach.items || coachQ.data,
    ).map(asRecord);
    const fromSignals = asList(
      asRecord(signalsQ.data).items ||
        asRecord(signalsQ.data).signals ||
        signalsQ.data,
    )
      .map(asRecord)
      .slice(0, 12)
      .map((s) => {
        const symbol = str(s.symbol || s.code, "—");
        const trend = str(s.trend || s.direction, "");
        const quality = str(s.quality || s.quality_score, "");
        const momentum = str(s.momentum || s.momentum_score, "");
        const rr = str(s.rr || s.expected_rr, "");
        const vol = str(s.volatility || s.atr, "");
        let text = `${symbol}`;
        if (trend) text += ` · ${trend}`;
        if (quality) text += ` · quality ${quality}`;
        if (momentum) text += ` · momentum ${momentum}`;
        if (rr) text += ` · RR ${rr}`;
        if (vol) text += ` · vol ${vol}`;
        return {
          title: `Watch ${symbol}`,
          detail: text,
          kind: "signal",
        };
      });
    const mapped = fromCoach.map((r) => ({
      title: str(r.title || r.symbol || r.action || "Recommendation"),
      detail: str(r.detail || r.message || r.reason || r.body, "—"),
      kind: str(r.kind || r.type, "coach"),
    }));
    return [...mapped, ...fromSignals];
  }, [coach, coachQ.data, signalsQ.data]);

  if (coachQ.isLoading && signalsQ.isLoading) return <DeskSkeleton rows={6} />;
  if (coachQ.isError && signalsQ.isError) {
    return (
      <DeskError
        message="Unable to load AI coach recommendations."
        onRetry={() => {
          void coachQ.refetch();
          void signalsQ.refetch();
        }}
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Badge tone="warning" className="h-5">
          Recommendations only
        </Badge>
        <p className="text-[12px] text-[var(--fg-muted)]">
          AI Coach never submits orders, never touches OMS / Gateway / Trading Core.
        </p>
      </div>

      {!recs.length ? (
        <DeskEmpty
          icon={GraduationCap}
          title="No recommendations yet"
          description="Coach advice appears from LIVE ecosystem coach + signal context when available."
        />
      ) : (
        <ul className="space-y-2">
          {recs.map((r, i) => (
            <li
              key={`${r.title}-${i}`}
              className="border border-[var(--border)] bg-[var(--surface)] px-3 py-3"
            >
              <div className="flex items-center gap-2">
                <h3 className="text-[13px] font-medium text-[var(--fg)]">{r.title}</h3>
                <Badge tone="neutral" className="h-5 px-1.5 text-[10px]">
                  {r.kind}
                </Badge>
              </div>
              <p className="mt-1 text-[12px] text-[var(--fg-muted)]">{r.detail}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
