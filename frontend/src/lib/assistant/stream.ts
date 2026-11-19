import { env, getRuntimeApiBaseUrl } from "@/lib/env";
import { getAccessToken } from "@/lib/auth/session";
import { parseSseFrame, streamBaseCandidates } from "@/lib/assistant/sse";

export type AssistantMeta = {
  as_of_utc?: string;
  bid?: number | null;
  ask?: number | null;
  source?: string;
  session?: string;
  bias?: string;
  assistant?: string;
};

export type AssistantStage = {
  key: string;
  label: string;
  detail?: string;
  status: "active" | "done";
};

export type StreamHandlers = {
  onMeta: (meta: AssistantMeta) => void;
  onDelta: (text: string) => void;
  onStage?: (stage: AssistantStage) => void;
  onThinking?: (text: string) => void;
};

export class AssistantStreamError extends Error {
  constructor(
    message: string,
    public code: string,
    /** True when nothing was streamed yet, so a non-streaming retry is safe. */
    public beforeFirstToken: boolean,
    public status = 0,
  ) {
    super(message);
  }
}

/** POST /intelligence/assistant/stream and feed deltas to the handlers. */
export async function streamAssistant(
  body: { message: string; history: { role: "user" | "assistant"; content: string }[]; images: string[] },
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const token = getAccessToken();
  if (!token) throw new AssistantStreamError("Sign in required", "auth", true, 401);
  // Stream straight from the API origin when possible: a CDN rewrite proxy
  // may hold the stream back. Network/CORS failure → try the next base.
  let res: Response | null = null;
  let lastError: unknown = null;
  for (const base of streamBaseCandidates(env.apiBaseUrl, getRuntimeApiBaseUrl())) {
    try {
      res = await fetch(`${base}/intelligence/assistant/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(body),
        signal,
      });
      break;
    } catch (error) {
      if (signal?.aborted) throw error;
      lastError = error;
    }
  }
  if (!res) throw lastError ?? new TypeError("Network error");
  if (!res.ok || !res.body) {
    let message = "QuantForg AI could not answer right now. Please try again.";
    let code = `http_${res.status}`;
    try {
      const payload = (await res.json()) as Record<string, unknown>;
      const detail = (payload.detail ?? (payload.error as Record<string, unknown>)?.details) as
        | Record<string, unknown>
        | undefined;
      const err = (payload.error ?? {}) as Record<string, unknown>;
      message =
        (typeof detail?.message === "string" && detail.message) ||
        (typeof err.message === "string" && err.message) ||
        message;
      code = (typeof detail?.code === "string" && detail.code) || code;
    } catch {
      /* keep defaults */
    }
    throw new AssistantStreamError(message, code, true, res.status);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let gotText = false;
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) >= 0) {
      const frame = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      const parsed = parseSseFrame(frame);
      if (!parsed) continue;
      const { event, data } = parsed;
      if (event === "meta") {
        handlers.onMeta(data as AssistantMeta);
      } else if (event === "stage") {
        handlers.onStage?.(data as unknown as AssistantStage);
      } else if (event === "thinking") {
        const text = String(data.text ?? "");
        if (text) handlers.onThinking?.(text);
      } else if (event === "delta") {
        const text = String(data.text ?? "");
        if (text) {
          gotText = true;
          handlers.onDelta(text);
        }
      } else if (event === "error") {
        throw new AssistantStreamError(
          String(data.message ?? "QuantForg AI could not answer right now."),
          String(data.code ?? "error"),
          !gotText,
        );
      } else if (event === "done") {
        return;
      }
    }
  }
  if (!gotText) throw new AssistantStreamError("The answer was interrupted.", "interrupted", true);

}
