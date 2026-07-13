"use client";

import { PageHeader } from "@/components/layout/page-header";
import { OrderTicket } from "@/components/trading/order-ticket";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function ExecutionPage() {
  return (
    <div>
      <PageHeader
        title="Execution Center"
        description="Validate, gate, and review execution requests. Live order_send remains disabled until the API enables it."
      />
      <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
        <OrderTicket />
        <Card>
          <CardHeader>
            <CardTitle>Desk policy</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-[var(--fg-muted)]">
            <p>1. Validate symbol constraints and volume steps via MT5 order validation.</p>
            <p>2. Run execution safety / risk pre-check with idempotent request IDs.</p>
            <p>3. Submit only when EXECUTION_ENABLED is true on the server.</p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
