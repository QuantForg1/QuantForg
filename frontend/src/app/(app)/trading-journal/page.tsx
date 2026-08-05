"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { TradingJournalWorkspace } from "@/components/operator/trading-journal-workspace";

export default function Page() {
  return (
    <div>
      <PageHeader
        title="Trading Journal"
        description="Every LIVE closed trade becomes a journal entry — search, filters, notes, CSV/PDF."
      />
      <PageMotion>
        <TradingJournalWorkspace />
      </PageMotion>
    </div>
  );
}
