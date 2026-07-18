"use client";

import dynamic from "next/dynamic";
import { DeskSkeleton } from "@/components/desk/primitives";

const BookShell = dynamic(
  () => import("@/components/book/shell").then((m) => m.BookShell),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full items-center justify-center p-6">
        <DeskSkeleton variant="page" />
      </div>
    ),
  },
);

/** Flagship Book OS — portfolio operating system. */
export default function BookPage() {
  return (
    <div className="h-full min-h-0 w-full">
      <BookShell />
    </div>
  );
}
