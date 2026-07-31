import { redirect } from "next/navigation";

/** Legacy mock payment success — replaced by contact request confirmation. */
export default function PurchaseSuccessRedirectPage() {
  redirect("/contact/success");
}
