"use client";

import dynamic from "next/dynamic";
import { Skeleton } from "@/components/ui/skeleton";

export const LazyEquityChart = dynamic(
  () => import("@/components/charts/equity-chart").then((m) => m.EquityChart),
  {
    ssr: false,
    loading: () => <Skeleton className="h-64 w-full" />,
  },
);

export const LazyBarChart = dynamic(
  () => import("@/components/charts/bar-chart").then((m) => m.DeskBarChart),
  {
    ssr: false,
    loading: () => <Skeleton className="h-64 w-full" />,
  },
);
