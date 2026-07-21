/** Map API / broker / pipeline failures to operator-visible messages — never "Submit failed". */

import { ApiError } from "@/lib/api/client";
import { asList, asRecord, num, str } from "@/lib/desk";
import { humanExecutionError } from "@/lib/execution/humanize";

function detailString(details: unknown): string {
  const d = asRecord(details);
  const reasons = asList(d.rejection_reasons ?? d.reasons ?? d.errors)
    .map(String)
    .filter(Boolean);
  const stages = asList(d.stages).map(asRecord);
  const failedStage = stages.find((s) => {
    const status = str(s.status).toLowerCase();
    return status === "failed" || status === "blocked" || status === "reject";
  });
  const stageReason = failedStage
    ? str(failedStage.reason ?? failedStage.comment)
    : "";
  const retcode = num(d.retcode, NaN);
  const comment = str(d.comment ?? d.message);
  const parts = [
    ...reasons.slice(0, 3),
    stageReason,
    comment,
    Number.isFinite(retcode) && retcode > 0 ? `Retcode ${retcode}` : "",
  ].filter(Boolean);
  return [...new Set(parts)].join(" · ");
}

/** Prefer broker / risk / gateway text over generic HTTP status copy. */
export function formatSubmitFailure(error: unknown): {
  title: string;
  description?: string;
} {
  if (error instanceof ApiError) {
    const fromDetails = detailString(error.details);
    const human = humanExecutionError(
      {
        message: error.message,
        retcode: asRecord(error.details).retcode,
        rejection_reasons: asList(
          asRecord(error.details).rejection_reasons ??
            asRecord(error.details).reasons,
        ),
        messages: fromDetails ? [fromDetails] : undefined,
        comment: str(asRecord(error.details).comment),
      },
      error.message || "Order rejected",
    );
    const title =
      human.title && !/^submit failed$/i.test(human.title)
        ? human.title
        : fromDetails ||
          error.message ||
          (error.code === "execution_disabled"
            ? "Live execution is disabled (EXECUTION_ENABLED=false)"
            : "Order rejected by server");
    const description = [
      human.description,
      fromDetails && fromDetails !== title ? fromDetails : "",
      error.code ? `Code ${error.code}` : "",
      error.requestId ? `Request ${error.requestId}` : "",
      error.status ? `HTTP ${error.status}` : "",
    ]
      .filter(Boolean)
      .filter((p, i, arr) => arr.indexOf(p) === i && p !== title)
      .join(" · ");
    return { title, description: description || undefined };
  }

  if (error instanceof TypeError || error instanceof DOMException) {
    return {
      title: "Cannot reach execution API",
      description:
        error.message ||
        "Network error — check API base URL, CORS, and gateway connectivity.",
    };
  }

  if (error && typeof error === "object") {
    const rec = asRecord(error);
    const human = humanExecutionError(rec, "Order rejected");
    if (human.title && !/^submit failed$/i.test(human.title)) {
      return human;
    }
  }

  if (error instanceof Error && error.message.trim()) {
    return {
      title: error.message,
      description: "Unexpected client error during submit.",
    };
  }

  return {
    title: "Order rejected",
    description: "No broker or server reason was returned — check Execution Audit.",
  };
}

export type ExecutionStageId =
  | "idle"
  | "validating"
  | "risk"
  | "sending"
  | "broker"
  | "completed"
  | "rejected";

export const EXECUTION_STAGE_LABEL: Record<ExecutionStageId, string> = {
  idle: "Ready",
  validating: "Validating…",
  risk: "Checking Risk…",
  sending: "Sending Order…",
  broker: "Broker Confirmation…",
  completed: "Completed",
  rejected: "Rejected",
};
