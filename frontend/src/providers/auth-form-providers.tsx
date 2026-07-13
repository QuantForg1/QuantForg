"use client";

import { Toaster } from "sonner";
import { AuthProvider } from "@/providers/auth-provider";

/** Lightweight providers for public auth forms (no React Query / realtime). */
export function AuthFormProviders({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
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
