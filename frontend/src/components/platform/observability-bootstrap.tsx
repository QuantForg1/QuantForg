"use client";

import { useEffect } from "react";
import { installErrorMonitoring } from "@/lib/observability/error-monitor";

/** Bootstraps global error + rejection listeners once per app session. */
export function ObservabilityBootstrap() {
  useEffect(() => {
    installErrorMonitoring();
  }, []);
  return null;
}
