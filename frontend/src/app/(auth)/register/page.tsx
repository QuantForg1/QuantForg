import { redirect } from "next/navigation";

/** Public self-service registration removed — licenses are provisioned manually. */
export default function RegisterRedirectPage() {
  redirect("/contact");
}
