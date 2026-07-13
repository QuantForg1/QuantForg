"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";

export default function AppError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("app_route_error", {
      message: error.message,
      digest: error.digest,
    });
  }, [error]);

  return (
    <div className="mx-auto flex min-h-[40vh] max-w-lg flex-col items-start justify-center gap-4 p-6">
      <h1 className="text-xl font-semibold text-[var(--fg)]">Unable to load this page</h1>
      <p className="text-sm text-[var(--fg-muted)]">
        A client error interrupted rendering. Retry to continue, or navigate elsewhere from the
        sidebar.
      </p>
      <Button onClick={reset}>Retry</Button>
    </div>
  );
}
