"use client";

import { memo } from "react";
import type { RefObject } from "react";
import {
  ExecutionOrderTicket,
  type OrderTicketHandle,
} from "@/components/execution/order-ticket";

/** One order ticket — no duplicate account summary (lives on SessionBar). */
export const TerminalRightRail = memo(function TerminalRightRail({
  symbol,
  onSymbolChange,
  connected,
  bid,
  ask,
  ticketRef,
}: {
  symbol: string;
  onSymbolChange: (s: string) => void;
  connected: boolean;
  bid?: number;
  ask?: number;
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
          dense
        />
      </div>
    </aside>
  );
});
