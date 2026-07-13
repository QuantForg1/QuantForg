"use client";

import dynamic from "next/dynamic";
import { Skeleton } from "@/components/ui/skeleton";

export const LazyEquityChart = dynamic(
  () => import("@/components/charts/equity-chart").then((m) => m.EquityChart),
  { ssr: false, loading: () => <Skeleton className="h-64 w-full" /> },
);

export const LazyBarChart = dynamic(
  () => import("@/components/charts/bar-chart").then((m) => m.DeskBarChart),
  { ssr: false, loading: () => <Skeleton className="h-64 w-full" /> },
);

export const LazyTerminalEquityChart = dynamic(
  () =>
    import("@/components/charts/terminal-equity-chart").then((m) => m.TerminalEquityChart),
  { ssr: false, loading: () => <Skeleton className="h-72 w-full" /> },
);

export const LazyDonutChart = dynamic(
  () => import("@/components/charts/donut-chart").then((m) => m.DonutChart),
  { ssr: false, loading: () => <Skeleton className="h-56 w-full" /> },
);

export const LazySparkline = dynamic(
  () => import("@/components/charts/sparkline").then((m) => m.Sparkline),
  { ssr: false, loading: () => <Skeleton className="h-8 w-full" /> },
);
