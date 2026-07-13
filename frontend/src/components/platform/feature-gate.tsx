"use client";

import Link from "next/link";
import { isFeatureEnabled, type FeatureFlagKey } from "@/lib/platform/flags";
import { DeskEmpty } from "@/components/desk/primitives";
import { ShieldOff } from "lucide-react";

export function FeatureGate({
  flag,
  children,
  label,
}: {
  flag: FeatureFlagKey;
  children: React.ReactNode;
  label?: string;
}) {
  if (isFeatureEnabled(flag)) return <>{children}</>;
  return (
    <div className="p-6">
      <DeskEmpty
        icon={ShieldOff}
        title={`${label || flag} is disabled`}
        description="This capability is turned off by a production feature flag. Contact an operator to enable it."
        actionLabel="Operations"
        onAction={() => {
          window.location.href = "/ops";
        }}
      />
      <p className="mt-3 text-center text-xs text-[var(--fg-muted)]">
        <Link href="/dashboard" className="text-[var(--accent)]">
          Back to dashboard
        </Link>
      </p>
    </div>
  );
}
