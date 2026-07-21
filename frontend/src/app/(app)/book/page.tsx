"use client";

import { redirect } from "next/navigation";

/** Legacy Book route — Portfolio OS is canonical. */
export default function BookPage() {
  redirect("/portfolio");
}
