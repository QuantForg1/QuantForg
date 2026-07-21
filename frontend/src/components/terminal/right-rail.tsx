"use client";

import { memo } from "react";
import type { RefObject } from "react";
import {
  ExecutionOrderTicket,
  type OrderTicketHandle,
} from "@/components/execution/order-ticket";

/** Order ticket only — risk and ops live on dedicated workspaces. */
export const TerminalRightRail = memo(function TerminalRightRail({
  symbol,
  onSymbolChange,
  connected,
  bid,
  ask,
  tickTimeMs,
  ticketRef,
}: {
  symbol: string;
  onSymbolChange: (s: string) => void;
  connected: boolean;
  bid?: number;
  ask?: number;
  tickTimeMs?: number | null;
  ticketRef: RefObject<OrderTicketHandle | null>;
}) {
  return (
    <aside
      className="flex h-full min-h-0 flex-col border-l border-[var(--border)] bg-[var(--bg-elevated)]"
      aria-label="Order ticket"
    >
      <div className="min-h-0 flex-1 overflow-y-auto">
        <ExecutionOrderTicket
          ref={ticketRef}
          symbol={symbol}
          onSymbolChange={onSymbolChange}
          connected={connected}
          bid={bid}
          ask={ask}
          tickTimeMs={tickTimeMs}
          dense
        />
      </div>
    </aside>
  );
});
