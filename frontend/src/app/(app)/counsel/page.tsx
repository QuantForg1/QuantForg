"use client";

import { redirect } from "next/navigation";

/** Legacy Counsel route — AI Signals is canonical. */
export default function CounselPage() {
  redirect("/ai-signals");
}
