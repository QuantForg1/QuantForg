"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { Toaster } from "sonner";
import { OfflineBanner } from "@/components/system/offline-banner";
import { AuthProvider } from "@/providers/auth-provider";

/** Providers for public Live Market surfaces (auth optional + React Query). */
export function PublicMarketProviders({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            refetchOnWindowFocus: false,
            retry: 1,
          },
        },
      }),
  );

  return (
    <AuthProvider>
      <QueryClientProvider client={client}>
        <OfflineBanner />
        {children}
        <Toaster
          theme="dark"
          position="top-right"
          toastOptions={{
            className:
              "rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] text-[var(--fg)]",
          }}
        />
      </QueryClientProvider>
    </AuthProvider>
  );
}
