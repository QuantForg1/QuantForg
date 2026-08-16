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
  marketOpen = null,
  symbolAvailable = null,
  ticketRef,
}: {
  symbol: string;
  onSymbolChange: (s: string) => void;
  connected: boolean;
  bid?: number;
  ask?: number;
  tickTimeMs?: number | null;
  /** Explicit market session from tick API; null = unknown. */
  marketOpen?: boolean | null;
  /** Catalogue/symbol known independently of quotes. */
  symbolAvailable?: boolean | null;
  ticketRef: RefObject<OrderTicketHandle | null>;
}) {
  return (
    <aside
      className="flex h-full min-h-0 flex-col border-l border-[var(--border)] bg-[var(--bg-elevated)]"
      aria-label="Order ticket"
    >
      <div className="flex h-7 shrink-0 items-center justify-between gap-2 border-b border-[var(--border)] px-2.5">
        <p className="text-[10px] font-medium uppercase tracking-[0.08em] text-[var(--fg-subtle)]">
          Ticket
        </p>
        <span className="text-[10px] text-[var(--fg-subtle)]">B / S</span>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
        <ExecutionOrderTicket
          ref={ticketRef}
          symbol={symbol}
          onSymbolChange={onSymbolChange}
          connected={connected}
          bid={bid}
          ask={ask}
          tickTimeMs={tickTimeMs}
          marketOpen={marketOpen}
          symbolAvailable={symbolAvailable}
          dense
        />
      </div>
    </aside>
  );
});
