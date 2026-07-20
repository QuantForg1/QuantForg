"use client";

import { OrdersHistoryDesk } from "@/components/journal/orders-history";

export default function JournalOrdersPage() {
  return (
    <div className="h-[calc(100dvh-3.5rem)] overflow-hidden bg-[var(--bg)]">
      <OrdersHistoryDesk />
    </div>
  );
}
