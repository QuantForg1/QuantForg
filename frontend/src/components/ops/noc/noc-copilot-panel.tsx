"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { asList, asRecord, str } from "@/lib/desk";
import { NocPanel } from "@/components/ops/noc/noc-primitives";

const PROMPTS = [
  "Why isn't QuantForg trading?",
  "Why was the last trade rejected?",
  "Show execution failures today.",
  "Show broker latency.",
  "Summarize production health.",
];

export function NocCopilotPanel({
  onAsk,
  loading,
  result,
  error,
}: {
  onAsk: (question: string) => Promise<unknown>;
  loading: boolean;
  result: unknown;
  error: unknown;
}) {
  const [question, setQuestion] = useState(PROMPTS[0] ?? "");
  const data = asRecord(result);
  const evidence = asList(data.evidence).map(String);

  return (
    <NocPanel title="AI Operations Copilot">
      <p className="mb-2 text-[11px] text-[var(--fg-muted)]">
        Answers only from live NOC telemetry. Never invents trades or metrics.
      </p>
      <div className="mb-2 flex flex-wrap gap-1">
        {PROMPTS.map((p) => (
          <button
            key={p}
            type="button"
            className="border border-[var(--border)] px-1.5 py-0.5 text-[10px] text-[var(--fg-muted)] hover:bg-[var(--surface-2)]"
            onClick={() => setQuestion(p)}
          >
            {p}
          </button>
        ))}
      </div>
      <textarea
        className="min-h-[72px] w-full border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5 text-[12px] text-[var(--fg)]"
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        aria-label="Copilot question"
      />
      <Button
        size="sm"
        className="mt-2 w-full"
        disabled={loading || !question.trim()}
        onClick={() => void onAsk(question.trim())}
      >
        {loading ? "Querying telemetry…" : "Ask"}
      </Button>
      {error ? (
        <p className="mt-2 text-[11px] text-[var(--danger)]">
          {error instanceof Error ? error.message : "Copilot request failed"}
        </p>
      ) : null}
      {data.answer ? (
        <div className="mt-3 border border-[var(--border)] bg-[var(--surface-2)] px-2 py-2">
          <div className="mb-1 flex items-center gap-2">
            <Badge tone="accent">Grounded</Badge>
            {data.hallucination_guard ? (
              <Badge tone="success">No hallucination</Badge>
            ) : null}
          </div>
          <pre className="whitespace-pre-wrap font-sans text-[12px] text-[var(--fg)]">
            {str(data.answer)}
          </pre>
          {evidence.length > 0 ? (
            <ul className="mt-2 max-h-28 space-y-0.5 overflow-auto font-mono text-[10px] text-[var(--fg-subtle)]">
              {evidence.map((e) => (
                <li key={e}>· {e}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </NocPanel>
  );
}
