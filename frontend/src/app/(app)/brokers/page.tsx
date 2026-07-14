import { redirect } from "next/navigation";

/** Legacy multi-broker entry — production routes to Broker Workspace. */
export default function BrokersRedirectPage() {
  redirect("/broker");
}
