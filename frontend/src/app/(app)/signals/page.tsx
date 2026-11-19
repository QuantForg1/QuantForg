"use client";

import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/layout/page-header";
import { DeskSkeleton } from "@/components/desk/primitives";
import { SignalsLockedView } from "@/components/billing/feature-locked";
import { SignalsWorkspace } from "@/components/trading/signals-workspace";
import { billingApi } from "@/lib/api/endpoints";
import { asRecord } from "@/lib/desk";
import { signalsAccess } from "@/lib/billing/feature-access";

export default function SignalsPage() {
  const meQ = useQuery({
    queryKey: ["billing-me"],
    queryFn: () => billingApi.me(),
    retry: false,
    staleTime: 15_000,
  });
  const access = signalsAccess({
    loading: meQ.isLoading,
    error: meQ.isError,
    robotAccess: asRecord(asRecord(meQ.data).robot_access),
  });

  if (access === "checking") {
    return (
      <div className="qf-desk min-w-0 space-y-5">
        <PageHeader eyebrow="Research" title="Signals" description="Checking your plan…" />
        <DeskSkeleton />
      </div>
    );
  }
  if (access === "locked") return <SignalsLockedView />;
  // "open", or billing unreadable: the API is the final gate (402 → locked).
  return <SignalsWorkspace />;
}
