"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { connectMt5Action } from "@/lib/trading/connect-mt5";
import { useTradingSession } from "@/providers/trading-session-provider";

/** Terminal / empty-state Connect MT5 — configure, reconnect, or no-op. */
export function useConnectMt5() {
  const router = useRouter();
  const qc = useQueryClient();
  const session = useTradingSession();
  const [pending, setPending] = useState(false);

  const connect = useCallback(async () => {
    if (pending) return;
    setPending(true);
    try {
      const result = await connectMt5Action({ connected: session.connected });
      switch (result.outcome) {
        case "already_connected":
          toast.message("Broker already connected");
          return;
        case "not_configured":
          router.push(result.href);
          return;
        case "reconnected":
          toast.success("Broker reconnecting…");
          await Promise.all([
            qc.invalidateQueries({ queryKey: ["mt5-status"] }),
            qc.invalidateQueries({ queryKey: ["weltrade-health"] }),
            qc.invalidateQueries({ queryKey: ["weltrade-dashboard"] }),
          ]);
          await session.invalidateAll();
          return;
        case "gateway_unavailable":
          toast.error(result.message || "Gateway unavailable");
          return;
        case "auth_failed":
          toast.error(result.message || "Broker authentication failed");
          router.push("/broker");
          return;
        default:
          toast.error(result.message || "Connection failed");
      }
    } finally {
      setPending(false);
    }
  }, [pending, qc, router, session]);

  return { connect, pending };
}
