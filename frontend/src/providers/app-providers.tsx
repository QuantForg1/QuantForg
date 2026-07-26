"use client";

import { AppShell } from "@/components/layout/app-shell";
import { AuthLayoutProviders } from "@/providers/auth-layout-providers";
import { RealtimeProvider } from "@/providers/realtime-provider";
import { TradingSessionProvider } from "@/providers/trading-session-provider";
import { ObservabilityBootstrap } from "@/components/platform/observability-bootstrap";
import {
  BetaBanner,
  BetaInviteGate,
  MaintenanceGate,
} from "@/components/platform/beta-controls";
import { FirstRunChecklist } from "@/components/platform/first-run-checklist";
import { ProductTour } from "@/components/platform/product-tour";
import { TooltipProvider } from "@/components/ui/tooltip";

export function AppProviders({ children }: { children: React.ReactNode }) {
  return (
    <AuthLayoutProviders>
      <ObservabilityBootstrap />
      <RealtimeProvider>
        <TradingSessionProvider>
        <TooltipProvider delayDuration={320} skipDelayDuration={100}>
        <MaintenanceGate>
          <BetaInviteGate>
            <div className="flex min-h-0 flex-1 flex-col">
              <BetaBanner />
              <FirstRunChecklist />
              <ProductTour />
              <AppShell>{children}</AppShell>
            </div>
          </BetaInviteGate>
        </MaintenanceGate>
        </TooltipProvider>
        </TradingSessionProvider>
      </RealtimeProvider>
    </AuthLayoutProviders>
  );
}
