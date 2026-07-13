"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  getBetaState,
  isBetaGateBlocking,
  isMaintenanceBlocking,
  unlockBeta,
} from "@/lib/platform/beta";
import { recordAudit } from "@/lib/observability/audit";
import { getBuildVersion } from "@/lib/observability/context";

export function BetaBanner() {
  const [state, setState] = useState(() => getBetaState());

  useEffect(() => {
    setState(getBetaState());
  }, []);

  if (!state.betaMode && !state.readOnlyMode) return null;

  return (
    <div
      className="border-b border-[var(--border)] bg-[var(--warning-soft)] px-4 py-2 text-center text-xs text-[var(--fg)]"
      role="status"
    >
      {state.betaMode ? "Closed beta · " : null}
      Build {getBuildVersion()}
      {state.readOnlyMode ? " · Read-only mode enabled" : null}
      {state.maintenanceMode ? " · Maintenance window" : null}
    </div>
  );
}

export function MaintenanceGate({ children }: { children: React.ReactNode }) {
  if (!isMaintenanceBlocking()) return <>{children}</>;
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3 p-8 text-center">
      <h1 className="text-xl font-semibold text-[var(--fg)]">Maintenance in progress</h1>
      <p className="max-w-md text-sm text-[var(--fg-muted)]">
        QuantForg is temporarily unavailable while operators apply updates. Please retry shortly.
      </p>
    </div>
  );
}

export function BetaInviteGate({ children }: { children: React.ReactNode }) {
  const [blocked, setBlocked] = useState(false);
  const [code, setCode] = useState("");

  useEffect(() => {
    setBlocked(isBetaGateBlocking());
  }, []);

  if (!blocked) return <>{children}</>;

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 p-8">
      <div className="w-full max-w-sm space-y-3 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6">
        <h1 className="text-lg font-semibold">Closed beta access</h1>
        <p className="text-sm text-[var(--fg-muted)]">
          Enter your invite code to unlock the QuantForg closed beta.
        </p>
        <div className="space-y-1.5">
          <Label htmlFor="beta-code">Invite code</Label>
          <Input
            id="beta-code"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            autoComplete="one-time-code"
          />
        </div>
        <Button
          className="w-full"
          onClick={() => {
            if (unlockBeta(code)) {
              recordAudit("beta_unlock", "success", "Beta invite accepted");
              setBlocked(false);
              toast.success("Beta unlocked");
            } else {
              recordAudit("beta_unlock", "failure", "Beta invite rejected");
              toast.error("Invalid invite code");
            }
          }}
        >
          Unlock
        </Button>
      </div>
    </div>
  );
}
