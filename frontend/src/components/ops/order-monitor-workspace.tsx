"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { executionApi, portfolioApi } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { useOrdersStream } from "@/hooks/realtime";
import { useTradingSession } from "@/providers/trading-session-provider";
import { ListOrdered } from "lucide-react";

type Stage =
  | "pending"
  | "risk"
  | "oms"
  | "gateway"
  | "broker"
  | "accepted"
  | "rejected"
  | "pme"
  | "closed";

function stageOf(row: Record<string, unknown>): Stage {
  const blob = `${str(row.status)} ${str(row.state)} ${str(row.outcome)} ${str(row.stage)} ${str(row.execution_result)}`.toLowerCase();
  if (/reject|denied|fail/.test(blob)) return "rejected";
  if (/closed|filled|done|complete/.test(blob)) return "closed";
  if (/pme|manage|trail|protect/.test(blob)) return "pme";
  if (/accept|filled|submitted/.test(blob)) return "accepted";
  if (/broker|mt5/.test(blob)) return "broker";
  if (/gateway/.test(blob)) return "gateway";
  if (/oms|order/.test(blob)) return "oms";
  if (/risk/.test(blob)) return "risk";
  return "pending";
}

const STAGES: Stage[] = [
  "pending",
  "risk",
  "oms",
  "gateway",
  "broker",
  "accepted",
  "rejected",
  "pme",
  "closed",
];

/** LIVE order lifecycle monitor — portfolio orders + execution journal. */
export function OrderMonitorWorkspace() {
  const session = useTradingSession();
  useOrdersStream(session.connected);
  const [stage, setStage] = useState<Stage | "all">("all");

  const ordersQ = useQuery({
    queryKey: ["portfolio-orders", "order-monitor"],
    queryFn: () => portfolioApi.orders(),
    staleTime: 8_000,
    refetchInterval: 12_000,
    retry: false,
  });
  const journalQ = useQuery({
    queryKey: ["execution-journal", "order-monitor"],
    queryFn: () => executionApi.journal(100),
    staleTime: 10_000,
    refetchInterval: 15_000,
    retry: false,
  });

  const rows = useMemo(() => {
    const orders = asList(ordersQ.data).map(asRecord);
    const journal = asList(
      asRecord(journalQ.data).items ||
        asRecord(journalQ.data).events ||
        asRecord(journalQ.data).journal ||
        journalQ.data,
    ).map(asRecord);
    const merged: Array<Record<string, unknown> & { _stage: Stage }> = [
      ...orders,
      ...journal,
    ].map((r) => ({
      ...r,
      _stage: stageOf(r),
    }));
    return stage === "all" ? merged : merged.filter((r) => r._stage === stage);
  }, [journalQ.data, ordersQ.data, stage]);

  if (ordersQ.isLoading && journalQ.isLoading && !rows.length) {
    return <DeskSkeleton rows={8} />;
  }
  if (ordersQ.isError && journalQ.isError) {
    return (
      <DeskError
        message="Unable to load order lifecycle."
        onRetry={() => {
          void ordersQ.refetch();
          void journalQ.refetch();
        }}
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          variant={stage === "all" ? "default" : "outline"}
          onClick={() => setStage("all")}
        >
          All
        </Button>
        {STAGES.map((s) => (
          <Button
            key={s}
            size="sm"
            variant={stage === s ? "default" : "outline"}
            onClick={() => setStage(s)}
          >
            {s}
          </Button>
        ))}
        <Button asChild size="sm" variant="ghost">
          <Link href="/orders">Orders blotter</Link>
        </Button>
        <Button asChild size="sm" variant="ghost">
          <Link href="/executions">Executions</Link>
        </Button>
      </div>

      {!rows.length ? (
        <DeskEmpty
          icon={ListOrdered}
          title="No live order events"
          description="Pending → Risk → OMS → Gateway → Broker → Accepted/Rejected → PME → Closed appears from LIVE feeds."
        />
      ) : (
        <div className="overflow-x-auto border border-[var(--border)]">
          <table className="min-w-full text-left text-[12px]">
            <thead className="bg-[var(--surface)] text-[10px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
              <tr>
                <th className="px-3 py-2">Stage</th>
                <th className="px-3 py-2">Symbol</th>
                <th className="px-3 py-2">Side</th>
                <th className="px-3 py-2">Qty</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Time</th>
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, 200).map((r, i) => (
                <tr
                  key={str(r.id || r.ticket || r.request_id, String(i))}
                  className="border-t border-[var(--border)]"
                >
                  <td className="px-3 py-2">
                    <Badge tone="neutral" className="h-5 px-1.5 text-[10px]">
                      {r._stage}
                    </Badge>
                  </td>
                  <td className="px-3 py-2 font-mono">{str(r.symbol, "—")}</td>
                  <td className="px-3 py-2">{str(r.side || r.type, "—")}</td>
                  <td className="px-3 py-2 tabular">
                    {Number.isFinite(num(r.volume ?? r.qty))
                      ? String(num(r.volume ?? r.qty))
                      : "—"}
                  </td>
                  <td className="px-3 py-2">
                    {str(r.status || r.outcome || r.state, "—")}
                  </td>
                  <td className="px-3 py-2 font-mono text-[10px] text-[var(--fg-muted)]">
                    {str(r.time || r.at || r.created_at || r.timestamp, "—").slice(0, 19)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
