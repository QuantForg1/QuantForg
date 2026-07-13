"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";

export default function RootError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("root_error", {
      message: error.message,
      digest: error.digest,
    });
  }, [error]);

  return (
    <div className="mx-auto flex min-h-[50vh] max-w-lg flex-col items-start justify-center gap-4 p-6">
      <h1 className="text-xl font-semibold text-[var(--fg)]">Something went wrong</h1>
      <p className="text-sm text-[var(--fg-muted)]">
        An unexpected error interrupted this view. Retry to continue.
      </p>
      <Button onClick={reset}>Retry</Button>
    </div>
  );
}
