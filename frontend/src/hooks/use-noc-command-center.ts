"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { iteOpsApi, platformApi } from "@/lib/api/endpoints";
import { env } from "@/lib/env";

/** Efficient poll cadence for NOC — complements existing realtime fallback. */
const NOC_REFETCH_MS = 8_000;

export function useNocCommandCenter(enabled = true) {
  const noc = useQuery({
    queryKey: ["ite-ops-noc-command-center"],
    queryFn: iteOpsApi.nocCommandCenter,
    enabled,
    retry: false,
    refetchInterval: enabled ? NOC_REFETCH_MS : false,
    staleTime: 4_000,
  });

  const version = useQuery({
    queryKey: ["platform-version", "noc"],
    queryFn: platformApi.version,
    enabled,
    retry: false,
    refetchInterval: enabled ? 60_000 : false,
  });

  const healthLive = useQuery({
    queryKey: ["health-live", "noc"],
    queryFn: platformApi.healthLive,
    enabled,
    retry: false,
    refetchInterval: enabled ? 10_000 : false,
  });

  const copilot = useMutation({
    mutationFn: (question: string) => iteOpsApi.nocCopilot(question),
  });

  return {
    noc,
    version,
    healthLive,
    copilot,
    buildVersion: env.buildVersion,
    refetchMs: NOC_REFETCH_MS,
  };
}
