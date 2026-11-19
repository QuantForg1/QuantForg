/** Pure helpers for the admin portal (unit-tested). */

export type Tone = "success" | "warning" | "danger" | "neutral" | "accent";

export function userStatusTone(status: string): Tone {
  switch (status) {
    case "active":
      return "success";
    case "pending":
      return "neutral";
    case "suspended":
      return "warning";
    case "deactivated":
      return "danger";
    default:
      return "neutral";
  }
}

export function subscriptionTone(status: string): Tone {
  if (status === "active") return "success";
  if (status === "none" || !status) return "neutral";
  if (["expired", "revoked", "suspended", "payment_failed"].includes(status)) return "danger";
  return "warning";
}

export function brokerStatusTone(status: string): Tone {
  if (status === "active") return "success";
  if (status === "disabled") return "warning";
  if (status === "revoked") return "danger";
  return "neutral";
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return "—";
  return new Date(t).toLocaleString([], {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Which status actions make sense from the current status. */
export function statusActions(status: string): Array<"suspend" | "reactivate" | "deactivate"> {
  if (status === "suspended") return ["reactivate", "deactivate"];
  if (status === "deactivated") return ["reactivate"];
  return ["suspend", "deactivate"];
}

/** Which broker actions make sense from the current broker status. */
export function brokerActions(status: string): Array<"disable" | "enable" | "remove"> {
  if (status === "disabled") return ["enable", "remove"];
  if (status === "revoked") return [];
  return ["disable", "remove"];
}

export const ACTION_COPY: Record<string, { title: string; body: string; confirm: string; danger: boolean }> = {
  suspend: {
    title: "Suspend this user?",
    body: "They are signed out within a minute, cannot log in, and their robot stops opening new trades. Open positions keep their stop loss and take profit.",
    confirm: "Suspend user",
    danger: true,
  },
  reactivate: {
    title: "Reactivate this user?",
    body: "They can sign in again. Their robot stays stopped until they start it.",
    confirm: "Reactivate",
    danger: false,
  },
  deactivate: {
    title: "Deactivate this account?",
    body: "The account is closed: no sign-in and no trading. You can reactivate it later.",
    confirm: "Deactivate",
    danger: true,
  },
  disable: {
    title: "Disconnect this broker?",
    body: "The robot stops trading on it and its terminal slot is released. The account stays saved and can be enabled again.",
    confirm: "Disconnect broker",
    danger: true,
  },
  enable: {
    title: "Enable this broker again?",
    body: "The account becomes available to the robot again. The robot itself stays stopped until the user starts it.",
    confirm: "Enable broker",
    danger: false,
  },
  remove: {
    title: "Remove this broker permanently?",
    body: "The account and its stored password are revoked. This cannot be undone; the user must connect it again.",
    confirm: "Remove broker",
    danger: true,
  },
};
