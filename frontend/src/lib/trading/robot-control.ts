/** Robot Control Center presentation helpers (state comes from the backend). */

export const ROBOT_ACTIONS = [
  "pause",
  "resume",
  "start",
  "stop",
  "emergency_stop",
] as const;
export type RobotAction = (typeof ROBOT_ACTIONS)[number];

/**
 * Label for the *control* setting. "RUNNING" here only means the owner of the
 * account allows the robot to trade; whether it actually trades is the
 * backend's `status` (see robotStatusTone).
 */
export function robotStateLabel(state: string): string {
  switch (state) {
    case "RUNNING":
      return "Enabled";
    case "PAUSED":
      return "Paused";
    case "STOPPED":
      return "Stopped";
    case "EMERGENCY_STOPPED":
      return "Emergency stopped";
    default:
      return state || "Unknown";
  }
}

export function robotStateTone(
  state: string,
): "success" | "warning" | "danger" | "neutral" {
  if (state === "RUNNING") return "success";
  if (state === "PAUSED" || state === "STOPPED") return "warning";
  if (state === "EMERGENCY_STOPPED") return "danger";
  return "neutral";
}

/** Verified connection states (backend evidence). Connected ≠ allowed to trade. */
export function connectionStateLabel(state: string): string {
  switch (state) {
    case "ROBOT_READY":
      return "Robot ready";
    case "CONNECTED":
      return "Connected · trade permission unknown";
    case "TRADING_PERMISSION_DISABLED":
      return "Connected · trading disabled by MT5";
    case "DEGRADED":
      return "Degraded";
    case "REQUIRES_USER_ACTION":
      return "Action required";
    case "NOT_CONNECTED":
      return "Not connected";
    case "UNAVAILABLE":
      return "Broker data unavailable · new entries blocked";
    default:
      return state || "Unknown";
  }
}

export function connectionStateTone(
  state: string,
): "success" | "warning" | "danger" | "neutral" {
  if (state === "ROBOT_READY") return "success";
  if (state === "CONNECTED" || state === "DEGRADED") return "warning";
  if (
    state === "TRADING_PERMISSION_DISABLED" ||
    state === "REQUIRES_USER_ACTION"
  )
    return "danger";
  return "neutral";
}

/** Tone for the backend-derived robot status (`status.code`). */
export function robotStatusTone(
  code: string,
): "success" | "warning" | "danger" | "neutral" {
  if (code === "ROBOT_RUNNING") return "success";
  if (code === "EMERGENCY_STOPPED") return "danger";
  if (code === "PAUSED" || code === "STOPPED" || code === "WAITING")
    return "warning";
  return "neutral";
}

export function robotActionLabel(action: RobotAction | string): string {
  return (
    {
      pause: "Pause",
      resume: "Resume",
      start: "Start",
      stop: "Stop",
      emergency_stop: "Emergency stop",
    } as Record<string, string>
  )[action] ?? "";
}

export type EditableRiskField = {
  key: string;
  label: string;
  help: string;
  unit: string;
};

const RISK_FIELD_ORDER = [
  "planned_risk_pct",
  "daily_loss_pct",
  "aggregate_open_risk_pct",
  "max_lot",
  "max_concurrent_positions",
];

/**
 * Only settings the backend marks as configurable for this user. Limits are
 * enforced on the server; no ceiling values are shown here.
 */
export function editableRiskFields(
  bounds: Record<string, unknown>,
): EditableRiskField[] {
  return RISK_FIELD_ORDER.filter((key) => {
    const b = bounds[key] as Record<string, unknown> | undefined;
    return Boolean(b && b.configurable === true);
  }).map((key) => {
    const b = bounds[key] as Record<string, unknown>;
    return {
      key,
      label: String(b.label ?? key),
      help: String(b.help ?? ""),
      unit: String(b.unit ?? ""),
    };
  });
}
