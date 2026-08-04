"use client";

import { Suspense } from "react";
import { useMemo } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { SignalIntelligenceWorkspace } from "@/components/ops/signal-intelligence-workspace";
import { Button } from "@/components/ui/button";
import { DeskSkeleton } from "@/components/desk/primitives";

const TABS = [
  "overview",
  "history",
  "outcomes",
  "probability",
  "heatmap",
  "analytics",
  "overlay",
] as const;

type Tab = (typeof TABS)[number];

function resolveTab(raw: string | null): Tab {
  if (raw && (TABS as readonly string[]).includes(raw)) return raw as Tab;
  return "overview";
}

function SignalIntelligenceBody() {
  const searchParams = useSearchParams();
  const initialTab = useMemo(
    () => resolveTab(searchParams.get("tab")),
    [searchParams],
  );

  return (
    <div>
      <PageHeader
        title="Signal Intelligence v2"
        description="LIVE signal history, outcomes, probability, heat map, chart overlay, and per-symbol analytics from real MT5 closes — never fabricated."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/signals">Signal Center</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/symbol-management">Symbol Management</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/admin/noc">NOC</Link>
            </Button>
          </div>
        }
      />
      <SignalIntelligenceWorkspace initialTab={initialTab} />
    </div>
  );
}

export default function SignalIntelligencePage() {
  return (
    <Suspense fallback={<DeskSkeleton rows={6} />}>
      <SignalIntelligenceBody />
    </Suspense>
  );
}
