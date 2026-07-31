import { redirect } from "next/navigation";

/** Legacy purchase URL — online checkout removed; sales are manual. */
export default function PurchaseRedirectPage() {
  redirect("/contact");
}
