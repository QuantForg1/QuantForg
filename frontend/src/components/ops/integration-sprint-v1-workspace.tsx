"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Cable, Shield } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { integrationSprintV1Api } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, str } from "@/lib/desk";
import { TRADING_SYMBOL } from "@/lib/trading/gold-only";
import { cn } from "@/lib/utils";

function Panel({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="border border-[var(--border)] bg-[var(--surface)]">
      <header className="border-b border-[var(--border)] px-3 py-2">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          {title}
        </h2>
      </header>
      <div className="p-3">{children}</div>
    </section>
  );
}

export function IntegrationSprintV1Workspace() {
  const qc = useQueryClient();
  const [bus, setBus] = useState<Record<string, unknown> | null>(null);

  const statusQ = useQuery({
    queryKey: ["integration-sprint-v1-status"],
    queryFn: () => integrationSprintV1Api.status(),
    staleTime: 15_000,
  });

  const refreshM = useMutation({
    mutationFn: () => integrationSprintV1Api.bus(),
    onSuccess: async (data) => {
      setBus(data);
      const summary = asRecord(data.health_summary);
      toast.success(
        `Bus · healthy ${str(summary.healthy, "0")} · missing ${str(summary.missing, "0")}`,
      );
      await qc.invalidateQueries({
        queryKey: ["integration-sprint-v1-status"],
      });
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Bus refresh failed"),
  });

  const caps = asRecord(statusQ.data?.capabilities);
  const connected = asList(asRecord(bus).connected_feeds);
  const missing = asList(asRecord(bus).missing_feeds);
  const health = asList(asRecord(bus).health);
  const summary = asRecord(asRecord(bus).health_summary);

  if (statusQ.isLoading && !statusQ.data) return <DeskSkeleton rows={6} />;
  if (statusQ.isError && !statusQ.data) {
    return (
      <DeskError
        message={
          statusQ.error instanceof ApiError
            ? statusQ.error.message
            : "Integration Sprint unavailable"
        }
      />
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
        <Cable className="size-4 text-[var(--fg-muted)]" />
        <span className="text-xs font-medium">
          {TRADING_SYMBOL} Integration Sprint V1
        </span>
        <Badge tone="accent" className="text-[9px] uppercase">
          Read-only bus
        </Badge>
        <Badge tone="success" className="text-[9px] uppercase">
          Never trades
        </Badge>
        {caps.preserves_existing_apis === true ? (
          <Badge tone="neutral" className="text-[9px] uppercase">
            APIs preserved
          </Badge>
        ) : null}
        <span className="ml-auto font-mono text-[10px] text-[var(--fg-subtle)]">
          {str(statusQ.data?.version, "integration-sprint-v1")}
        </span>
        <Button
          size="sm"
          disabled={refreshM.isPending}
          onClick={() => refreshM.mutate()}
        >
          Refresh data bus
        </Button>
      </div>

      <div className="grid gap-3 xl:grid-cols-3">
        <Panel title="Health summary">
          {!bus ? (
            <DeskEmpty
              icon={Cable}
              title="No snapshot"
              description="Refresh to probe MT5 · journal · calendar · warehouse"
            />
          ) : (
            <div className="space-y-1.5 text-xs">
              <div className="flex justify-between">
                <span className="text-[var(--fg-muted)]">Healthy</span>
                <span className="font-mono">{str(summary.healthy, "0")}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--fg-muted)]">Missing</span>
                <span className="font-mono">{str(summary.missing, "0")}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--fg-muted)]">Error</span>
                <span className="font-mono">{str(summary.error, "0")}</span>
              </div>
              <p className="text-[10px] text-[var(--fg-subtle)]">
                As of {str(bus.as_of, "—")}
              </p>
            </div>
          )}
        </Panel>

        <Panel title="Connected / missing">
          {!bus ? (
            <DeskEmpty
              icon={Shield}
              title="Await refresh"
              description="MISSING DATA reported — never fabricated"
            />
          ) : (
            <div className="grid grid-cols-2 gap-2 text-[10px]">
              <div>
                <p className="mb-1 text-[var(--fg-muted)]">Connected</p>
                <ul className="max-h-28 space-y-0.5 overflow-auto font-mono">
                  {connected.length === 0 ? (
                    <li className="text-[var(--fg-subtle)]">None</li>
                  ) : (
                    connected.map((f) => <li key={String(f)}>{String(f)}</li>)
                  )}
                </ul>
              </div>
              <div>
                <p className="mb-1 text-[var(--fg-muted)]">Missing</p>
                <ul className="max-h-28 space-y-0.5 overflow-auto font-mono">
                  {missing.length === 0 ? (
                    <li className="text-[var(--fg-subtle)]">None</li>
                  ) : (
                    missing.map((f) => <li key={String(f)}>{String(f)}</li>)
                  )}
                </ul>
              </div>
            </div>
          )}
        </Panel>

        <Panel title="Guarantees">
          <ul className="space-y-1 text-[10px] text-[var(--fg-muted)]">
            <li>Never places trades</li>
            <li>Never modifies Auto Trading / Execution</li>
            <li>Never modifies Decision / Risk / Safety</li>
            <li>Existing IVP / LLP / RMIP / PRC APIs preserved</li>
            <li>Hydrate → evaluate_body for existing /evaluate</li>
          </ul>
        </Panel>
      </div>

      <Panel title="Feed health">
        {!health.length ? (
          <DeskEmpty
            icon={Cable}
            title="No feeds"
            description="Trade · position · market · account · journal · …"
          />
        ) : (
          <ul className="grid gap-2 md:grid-cols-2 xl:grid-cols-5">
            {health.map((row) => {
              const h = asRecord(row);
              return (
                <li
                  key={str(h.feed)}
                  className={cn(
                    "border px-2 py-2",
                    h.status === "missing" || h.status === "error"
                      ? "border-[var(--warning)]/40"
                      : "border-[var(--border)]",
                  )}
                >
                  <p className="text-[10px] font-medium leading-tight">
                    {str(h.feed).replace(/_/g, " ")}
                  </p>
                  <p className="mt-1 font-mono text-[10px] text-[var(--fg-subtle)]">
                    {str(h.status)} · {str(h.latency_ms, "—")}ms
                  </p>
                  <p className="mt-1 text-[9px] text-[var(--fg-muted)] line-clamp-2">
                    {str(h.message)}
                  </p>
                </li>
              );
            })}
          </ul>
        )}
      </Panel>
    </div>
  );
}
