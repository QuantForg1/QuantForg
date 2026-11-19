import { redirect } from "next/navigation";

/** Risk Center retired. Trader risk lives on Robot & Risk. */
export default function RiskCenterPage() {
  redirect("/robot-control-center");
}
