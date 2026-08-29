"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { TradingJournalWorkspace } from "@/components/operator/trading-journal-workspace";

export default function Page() {
  return (
    <div>
      <PageHeader
        title="Journal"
        description="Closed trades, notes, and outcomes for your account. History is never fabricated."
      />
      <PageMotion>
        <TradingJournalWorkspace />
      </PageMotion>
    </div>
  );
}
