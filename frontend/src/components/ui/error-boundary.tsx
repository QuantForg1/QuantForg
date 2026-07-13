"use client";

import React from "react";
import { Button } from "@/components/ui/button";
import { captureError } from "@/lib/observability/error-monitor";

type State = { error: Error | null };

export class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  State
> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error) {
    captureError("react", error);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="rounded-xl border border-[var(--danger)]/40 bg-[var(--danger-soft)] p-6">
          <h2 className="text-lg font-semibold text-[var(--danger)]">Something went wrong</h2>
          <p className="mt-2 text-sm text-[var(--fg-muted)]">{this.state.error.message}</p>
          <Button className="mt-4" onClick={() => this.setState({ error: null })}>
            Try again
          </Button>
        </div>
      );
    }
    return this.props.children;
  }
}
