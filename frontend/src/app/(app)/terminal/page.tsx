"use client";

import dynamic from "next/dynamic";
import { Suspense } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { DeskSkeleton } from "@/components/desk/primitives";
import { Badge } from "@/components/ui/badge";
import { ConnectionStatus } from "@/components/trading/connection-status";
import { tradingSessionApi } from "@/lib/api/endpoints";
import { asRecord } from "@/lib/desk";
import {
  resolveConnectionPresentation,
  robotDisplayState,
} from "@/lib/trading/trader-ux";

const TerminalShell = dynamic(
  () => import("@/components/terminal/shell").then((m) => m.TerminalShell),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full items-center justify-center p-6">
        <DeskSkeleton variant="page" />
      </div>
    ),
  },
);

function robotTone(robot: string): "success" | "warning" | "danger" | "neutral" {
  if (robot === "RUNNING" || robot === "READY") return "success";
  if (robot === "PAUSED" || robot === "STOPPED") return "warning";
  return "danger";
}

/** Flagship Terminal OS — zero-scroll trading surface. */
export default function TerminalPage() {
  const sessionQ = useQuery({
    queryKey: ["trading-session"],
    queryFn: tradingSessionApi.session,
    retry: false,
    refetchInterval: 15_000,
  });
  const session = asRecord(sessionQ.data);
  const connection = resolveConnectionPresentation(session);
  const robot = robotDisplayState(session, connection);

  return (
    <div className="flex h-full min-h-0 w-full flex-col">
      <div className="flex shrink-0 flex-wrap items-center gap-2 border-b border-[var(--border)] bg-[var(--surface-2)] px-3 py-1.5">
        <ConnectionStatus session={session} compact />
        <Badge tone={robotTone(robot)}>{robot}</Badge>
        <Link
          href="/portfolio"
          className="text-[11px] font-medium text-[var(--fg-muted)] hover:text-[var(--accent)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
        >
          Positions
        </Link>
        <Link
          href="/signals"
          className="text-[11px] font-medium text-[var(--fg-muted)] hover:text-[var(--accent)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
        >
          Signals
        </Link>
      </div>
      <div className="min-h-0 flex-1">
        <Suspense
          fallback={
            <div className="flex h-full items-center justify-center p-6">
              <DeskSkeleton variant="page" />
            </div>
          }
        >
          <TerminalShell />
        </Suspense>
      </div>
    </div>
  );
}
