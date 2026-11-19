import { redirect } from "next/navigation";

/** History desk retired. Book remains the trader ledger. */
export default function HistoryPage() {
  redirect("/book");
}
