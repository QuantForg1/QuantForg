import { redirect } from "next/navigation";

/** Legacy multi-broker marketplace entry — production routes to Weltrade. */
export default function BrokersRedirectPage() {
  redirect("/broker");
}
