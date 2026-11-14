"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import Link from "next/link";
import {
  institutionalOpsApi,
  tradingSessionApi,
} from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { Button } from "@/components/ui/button";
import {
  Phase5Banner,
  Phase5Empty,
  Phase5Error,
  Phase5Loading,
  Phase5ModuleNav,
  Phase5Stat,
  Phase5TabBar,
} from "./shared";

type Tab = "overview" | "robots" | "queue" | "modules";

const TABS: { id: Tab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "robots", label: "Robot controls" },
  { id: "queue", label: "Work queue" },
  { id: "modules", label: "Modules" },
];

export function Phase5OperationsDesk() {
  const [tab, setTab] = useState<Tab>("overview");
  const [confirmStop, setConfirmStop] = useState(false);
  const qc = useQueryClient();

  const overviewQ = useQuery({
    queryKey: ["p5-ops-overview"],
    queryFn: institutionalOpsApi.operations,
    retry: false,
    staleTime: 10_000,
  });
  const robotQ = useQuery({
    queryKey: ["p5-robot-status"],
    queryFn: tradingSessionApi.robotStatus,
    retry: false,
    staleTime: 5_000,
  });

  const startM = useMutation({
    mutationFn: tradingSessionApi.startRobot,
    onSuccess: (data) => {
      toast.success("Start confirmed", {
        description: str(asRecord(data).run_state) || "running",
      });
      void qc.invalidateQueries({ queryKey: ["p5-robot-status"] });
      setConfirmStop(false);
    },
    onError: (err: Error) => toast.error("Start failed", { description: err.message }),
  });
  const pauseM = useMutation({
    mutationFn: tradingSessionApi.pauseRobot,
    onSuccess: (data) => {
      toast.success("Pause confirmed", {
        description: str(asRecord(data).run_state) || "paused",
      });
      void qc.invalidateQueries({ queryKey: ["p5-robot-status"] });
    },
    onError: (err: Error) => toast.error("Pause failed", { description: err.message }),
  });
  const stopM = useMutation({
    mutationFn: tradingSessionApi.stopRobot,
    onSuccess: (data) => {
      toast.success("Stop confirmed", {
        description: str(asRecord(data).run_state) || "off",
      });
      void qc.invalidateQueries({ queryKey: ["p5-robot-status"] });
      setConfirmStop(false);
    },
    onError: (err: Error) => toast.error("Stop failed", { description: err.message }),
  });

  const pending =
    startM.isPending || pauseM.isPending || stopM.isPending;

  if (overviewQ.isLoading) return <Phase5Loading />;
  if (overviewQ.isError) {
    return (
      <Phase5Error message="Operations overview unavailable — authenticate and retry." />
    );
  }

  const data = asRecord(overviewQ.data);
  const robot = asRecord(robotQ.data);
  const queue = asList(data.work_queue);
  const links = asList(data.module_links);

  return (
    <div>
      <Phase5ModuleNav current="/operations" />
      <Phase5Banner tone="ok">
        Observe-only Control Center hub. Robot mutations use authenticated{" "}
        <code className="font-mono">/trading/robot/*</code> APIs. Resume = Start
        after pause. Platform LIVE arm/enable stays on Admin Live Trading. Never
        reports success before backend confirmation.
      </Phase5Banner>
      <Phase5TabBar tabs={TABS} value={tab} onChange={setTab} />

      {tab === "overview" && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Phase5Stat
            label="Model"
            value={str(data.model_version) || "phase5-ops-1.0.0"}
          />
          <Phase5Stat
            label="Order send"
            value={data.never_order_send === false ? "enabled" : "blocked"}
            hint="Facade never submits LIVE orders"
          />
          <Phase5Stat
            label="Robot state"
            value={str(robot.run_state) || str(robot.status) || "unknown"}
          />
          <Phase5Stat label="Queue items" value={queue.length} />
        </div>
      )}

      {tab === "robots" && (
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-3">
            <Phase5Stat
              label="Run state"
              value={str(robot.run_state) || str(robot.status) || "—"}
            />
            <Phase5Stat
              label="Broker"
              value={str(robot.broker) || str(robot.account_login) || "—"}
            />
            <Phase5Stat
              label="Pending command"
              value={pending ? "in flight" : "idle"}
            />
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              disabled={pending}
              onClick={() => startM.mutate()}
            >
              Start / Resume
            </Button>
            <Button
              size="sm"
              variant="secondary"
              disabled={pending}
              onClick={() => pauseM.mutate()}
            >
              Pause
            </Button>
            {!confirmStop ? (
              <Button
                size="sm"
                variant="danger"
                disabled={pending}
                onClick={() => setConfirmStop(true)}
              >
                Stop…
              </Button>
            ) : (
              <Button
                size="sm"
                variant="danger"
                disabled={pending}
                onClick={() => stopM.mutate()}
              >
                Confirm stop
              </Button>
            )}
            <Button size="sm" variant="outline" asChild>
              <Link href="/admin/live-trading">Platform LIVE panel</Link>
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            Start after pause resumes the owned-account robot. Kill-switch and
            execution authorization remain authoritative on the backend.
          </p>
        </div>
      )}

      {tab === "queue" &&
        (queue.length === 0 ? (
          <Phase5Empty message="No operational work-queue items from AOC." />
        ) : (
          <ul className="divide-y divide-border/50 rounded-md border border-border/60">
            {queue.slice(0, 40).map((item, i) => {
              const row = asRecord(item);
              return (
                <li key={i} className="px-3 py-2 text-sm">
                  <div className="font-medium">
                    {str(row.title) || str(row.id) || `Item ${i + 1}`}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {str(row.status) || str(row.priority) || "queued"}
                  </div>
                </li>
              );
            })}
          </ul>
        ))}

      {tab === "modules" && (
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {(links.length
            ? links
            : [
                { path: "/strategy-lifecycle", label: "Strategy Lifecycle" },
                { path: "/execution-intelligence", label: "Execution Intelligence" },
                { path: "/account-orchestration", label: "Account Orchestration" },
                { path: "/risk-automation", label: "Risk Automation" },
                { path: "/incident-center", label: "Incident Center" },
                { path: "/governance", label: "Governance" },
              ]
          ).map((item, i) => {
            const row = asRecord(item);
            const href = str(row.path) || str(row.href) || "#";
            const label = str(row.label) || href;
            return (
              <Link
                key={i}
                href={href}
                className="rounded-md border border-border/60 bg-card/30 px-3 py-3 text-sm hover:border-accent/40"
              >
                {label}
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
