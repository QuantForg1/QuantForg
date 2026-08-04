"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/client";
import { iteReliabilityApi, weltradeApi } from "@/lib/api/endpoints";
import { asRecord } from "@/lib/desk";
import { useTradingSession } from "@/providers/trading-session-provider";
import { cn } from "@/lib/utils";

type Plane = "gateway" | "broker" | "mt5";

type RecoveryState = {
  attempt: number;
  nextAt: number | null;
  status: "idle" | "retrying" | "recovered" | "failed";
  message: string;
};

const INITIAL: RecoveryState = {
  attempt: 0,
  nextAt: null,
  status: "idle",
  message: "Standing by",
};

/**
 * Client-side recovery UX for Gateway / Broker / MT5.
 * Calls existing reconnect/recover endpoints only — no trading-core changes.
 * Auto mode is opt-in (max 3 retries + backoff) to avoid production spam.
 */
export function AutoRecoveryPanel() {
  const session = useTradingSession();
  const qc = useQueryClient();
  const [autoEnabled, setAutoEnabled] = useState(false);
  const [states, setStates] = useState<Record<Plane, RecoveryState>>({
    gateway: { ...INITIAL },
    broker: { ...INITIAL },
    mt5: { ...INITIAL },
  });
  const [now, setNow] = useState(() => Date.now());
  const firedRef = useRef<Record<Plane, number>>({
    gateway: 0,
    broker: 0,
    mt5: 0,
  });

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 500);
    return () => window.clearInterval(id);
  }, []);

  const healthQ = useQuery({
    queryKey: ["weltrade-health", "auto-recovery"],
    queryFn: weltradeApi.health,
    staleTime: 10_000,
    refetchInterval: 15_000,
    retry: 1,
  });
  const health = asRecord(healthQ.data);

  const gatewayDown = session.healthKnown
    ? !session.gatewayOnline
    : health.gateway_online === false;
  const brokerDown = session.healthKnown
    ? !session.brokerConnected
    : health.weltrade_connected === false;
  const mt5Down = session.healthKnown ? !session.connected : false;

  const reconnectMut = useMutation({
    mutationFn: async (plane: Plane) => {
      if (plane === "gateway") return iteReliabilityApi.recoverGateway();
      if (plane === "mt5") return iteReliabilityApi.recoverMt5();
      return weltradeApi.reconnect();
    },
    onSuccess: async (_data, plane) => {
      setStates((prev) => ({
        ...prev,
        [plane]: {
          attempt: prev[plane].attempt,
          nextAt: null,
          status: "recovered",
          message: "Recovered",
        },
      }));
      toast.success(`${plane} recovery requested`);
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["weltrade-health"] }),
        qc.invalidateQueries({ queryKey: ["mt5-status"] }),
        session.invalidateAll(),
      ]);
    },
    onError: (e, plane) => {
      const msg = e instanceof ApiError ? e.message : "Recovery failed";
      const attempt = states[plane].attempt;
      setStates((prev) => ({
        ...prev,
        [plane]: {
          ...prev[plane],
          status: "failed",
          message: msg,
          nextAt: Date.now() + Math.min(60_000, 5_000 * 2 ** attempt),
        },
      }));
      toast.error(msg);
    },
  });

  // Schedule automatic retries with backoff when auto mode is enabled.
  useEffect(() => {
    if (!autoEnabled) return;
    const planes: Array<{ id: Plane; down: boolean }> = [
      { id: "gateway", down: gatewayDown },
      { id: "broker", down: brokerDown },
      { id: "mt5", down: mt5Down },
    ];
    for (const p of planes) {
      if (!p.down) {
        setStates((prev) =>
          prev[p.id].status === "recovered" || prev[p.id].status === "idle"
            ? prev
            : {
                ...prev,
                [p.id]: { ...INITIAL, status: "recovered", message: "Recovered" },
              },
        );
        firedRef.current[p.id] = 0;
        continue;
      }
      setStates((prev) => {
        const cur = prev[p.id];
        if (cur.status === "retrying" && cur.nextAt && cur.nextAt > Date.now()) {
          return prev;
        }
        if (cur.attempt >= 3) {
          return {
            ...prev,
            [p.id]: {
              ...cur,
              status: "failed",
              message: "Max retries reached",
              nextAt: null,
            },
          };
        }
        if (cur.nextAt && cur.nextAt > Date.now()) return prev;
        const attempt = Math.min(3, cur.attempt + 1);
        const delay = Math.min(60_000, 4_000 * 2 ** (attempt - 1));
        return {
          ...prev,
          [p.id]: {
            attempt,
            nextAt: Date.now() + delay,
            status: "retrying",
            message: `Retry ${attempt}`,
          },
        };
      });
    }
  }, [autoEnabled, brokerDown, gatewayDown, mt5Down]);

  // Fire scheduled retries once per attempt.
  useEffect(() => {
    if (!autoEnabled) return;
    (["gateway", "broker", "mt5"] as Plane[]).forEach((plane) => {
      const cur = states[plane];
      if (cur.status !== "retrying" || !cur.nextAt) return;
      if (cur.nextAt > now) return;
      if (reconnectMut.isPending) return;
      if (firedRef.current[plane] >= cur.attempt) return;
      firedRef.current[plane] = cur.attempt;
      reconnectMut.mutate(plane);
    });
  }, [autoEnabled, now, reconnectMut, states]);

  const rows = useMemo(
    () =>
      (
        [
          ["gateway", "Gateway", gatewayDown],
          ["broker", "Broker", brokerDown],
          ["mt5", "MT5", mt5Down],
        ] as const
      ).map(([id, label, down]) => ({
        id,
        label,
        down,
        state: states[id],
      })),
    [brokerDown, gatewayDown, mt5Down, states],
  );

  return (
    <section className="border border-[var(--border)] bg-[var(--surface)]">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--border)] px-3 py-2">
        <div>
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Auto recovery
          </h2>
          <p className="text-[11px] text-[var(--fg-subtle)]">
            Backoff · heartbeat refresh · no page reload
          </p>
        </div>
        <Button
          size="sm"
          variant={autoEnabled ? "secondary" : "outline"}
          onClick={() => setAutoEnabled((v) => !v)}
        >
          {autoEnabled ? "Auto on" : "Auto off"}
        </Button>
      </header>
      <ul className="divide-y divide-[var(--border)]">
        {rows.map((row) => {
          const countdown =
            row.state.nextAt && row.state.nextAt > now
              ? Math.ceil((row.state.nextAt - now) / 1000)
              : null;
          return (
            <li
              key={row.id}
              className="flex flex-wrap items-center justify-between gap-3 px-3 py-2.5"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-[13px] font-medium text-[var(--fg)]">{row.label}</span>
                  <Badge
                    tone={
                      !row.down
                        ? "success"
                        : row.state.status === "retrying"
                          ? "warning"
                          : "danger"
                    }
                    className="h-5 px-1.5 text-[10px]"
                  >
                    {!row.down
                      ? "Connected"
                      : row.state.status === "retrying"
                        ? row.state.message
                        : row.state.status === "failed"
                          ? "Failed"
                          : "Disconnected"}
                  </Badge>
                </div>
                <p className={cn("text-[11px] text-[var(--fg-muted)]")}>
                  {countdown != null
                    ? `Next attempt in ${countdown}s`
                    : row.state.message}
                </p>
              </div>
              <Button
                size="sm"
                variant="outline"
                disabled={reconnectMut.isPending}
                onClick={() => {
                  setStates((prev) => ({
                    ...prev,
                    [row.id]: {
                      attempt: Math.min(3, prev[row.id].attempt + 1),
                      nextAt: null,
                      status: "retrying",
                      message: `Retry ${Math.min(3, prev[row.id].attempt + 1)}`,
                    },
                  }));
                  reconnectMut.mutate(row.id);
                }}
              >
                Retry now
              </Button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
