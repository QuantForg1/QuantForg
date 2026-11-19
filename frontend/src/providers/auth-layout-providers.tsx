"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { useState } from "react";
import { Toaster } from "sonner";
import { AuthProvider } from "@/providers/auth-provider";
import { isNetworkFailure } from "@/lib/api/connectivity";
import { ApiError } from "@/lib/api/client";

/** Client providers for authenticated / auth-form route groups. */
export function AuthLayoutProviders({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            refetchOnWindowFocus: false,
            // Brief network or server hiccups heal silently before any
            // message is shown; client errors (4xx) are not retried.
            retry: (failureCount, error) => {
              if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
                return false;
              }
              if (isNetworkFailure(error) || (error instanceof ApiError && error.status === 0)) {
                return failureCount < 2;
              }
              return failureCount < 2;
            },
            retryDelay: (attempt) => Math.min(1_000 * 2 ** attempt, 6_000),
          },
          mutations: {
            retry: false,
          },
        },
      }),
  );

  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="dark"
      forcedTheme="dark"
      enableSystem={false}
      storageKey="qf.theme.v3"
    >
      <QueryClientProvider client={client}>
        <AuthProvider>
          {children}
          <Toaster
            theme="dark"
            position="top-right"
            toastOptions={{
              className: "rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] text-[var(--fg)]",
            }}
          />
        </AuthProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
