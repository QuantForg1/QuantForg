"use client";

import { Toaster } from "sonner";
import { AuthProvider } from "@/providers/auth-provider";
import { OfflineBanner } from "@/components/system/offline-banner";

/** Lightweight providers for public auth forms (no React Query / realtime). */
export function AuthFormProviders({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <OfflineBanner />
      {children}
      <Toaster
        theme="dark"
        position="top-right"
        toastOptions={{
          className: "border border-[var(--border)] bg-[var(--surface)] text-[var(--fg)]",
        }}
      />
    </AuthProvider>
  );
}
