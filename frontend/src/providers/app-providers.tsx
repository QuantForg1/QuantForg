"use client";

import { AppShell } from "@/components/layout/app-shell";
import { AuthLayoutProviders } from "@/providers/auth-layout-providers";
import { RealtimeProvider } from "@/providers/realtime-provider";
import { ObservabilityBootstrap } from "@/components/platform/observability-bootstrap";
import { FeedbackWidget } from "@/components/platform/feedback-widget";
import {
  BetaBanner,
  BetaInviteGate,
  MaintenanceGate,
} from "@/components/platform/beta-controls";
import { FirstRunChecklist } from "@/components/platform/first-run-checklist";
import { ProductTour } from "@/components/platform/product-tour";

export function AppProviders({ children }: { children: React.ReactNode }) {
  return (
    <AuthLayoutProviders>
      <ObservabilityBootstrap />
      <RealtimeProvider>
        <MaintenanceGate>
          <BetaInviteGate>
            <div className="flex min-h-0 flex-1 flex-col">
              <BetaBanner />
              <FirstRunChecklist />
              <ProductTour />
              <AppShell>{children}</AppShell>
              <FeedbackWidget />
            </div>
          </BetaInviteGate>
        </MaintenanceGate>
      </RealtimeProvider>
    </AuthLayoutProviders>
  );
}
