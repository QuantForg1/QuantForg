"use client";

import { AppShell } from "@/components/layout/app-shell";
import { AuthLayoutProviders } from "@/providers/auth-layout-providers";
import { RealtimeProvider } from "@/providers/realtime-provider";

export function AppProviders({ children }: { children: React.ReactNode }) {
  return (
    <AuthLayoutProviders>
      <RealtimeProvider>
        <AppShell>{children}</AppShell>
      </RealtimeProvider>
    </AuthLayoutProviders>
  );
}
