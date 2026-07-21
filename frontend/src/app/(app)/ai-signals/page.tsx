"use client";

import dynamic from "next/dynamic";
import { DeskSkeleton } from "@/components/desk/primitives";

const CounselShell = dynamic(
  () => import("@/components/counsel/shell").then((m) => m.CounselShell),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full items-center justify-center p-6">
        <DeskSkeleton variant="page" />
      </div>
    ),
  },
);

/** AI Signals — Counsel decision operating system. */
export default function AiSignalsPage() {
  return (
    <div className="h-full min-h-0 w-full">
      <CounselShell />
    </div>
  );
}
