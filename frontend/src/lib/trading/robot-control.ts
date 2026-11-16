/** Robot Control Center presentation helpers (state comes from the backend). */

export const ROBOT_ACTIONS = [
    "pause",
    "resume",
    "start",
    "stop",
    "emergency_stop",
] as const;
export type RobotAction = (typeof ROBOT_ACTIONS)[number];

export function robotStateLabel(state: string): string {
    switch (state) {
        case "RUNNING":
            return "Running";
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
