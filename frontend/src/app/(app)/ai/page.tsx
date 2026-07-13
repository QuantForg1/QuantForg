"use client";

import { useState } from "react";
import { toast } from "sonner";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { env } from "@/lib/env";
import { FeatureGate } from "@/components/platform/feature-gate";
import { intelligenceApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { ApiError } from "@/lib/api/client";

type Msg = { role: "user" | "assistant"; content: string };

const starters = [
  "Summarize current market conditions",
  "What are my main risk factors?",
  "Explain portfolio exposure",
];

export default function AiPage() {
  const [messages, setMessages] = useState<Msg[]>([
    {
      role: "assistant",
      content:
        "Ask for an advisory summary grounded in live MT5 sync, market context, and configured news feeds. I will not invent facts or place trades.",
    },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  async function send(text: string) {
    if (!text.trim() || busy) return;
    const user: Msg = { role: "user", content: text };
    setBusy(true);
    setMessages((m) => [...m, user]);
    setInput("");
    try {
      if (env.useMockAi) {
        setMessages((m) => [
          ...m,
          {
            role: "assistant",
            content: `[mock] Received: “${text}”. Disable NEXT_PUBLIC_MOCK_AI to use the real advisor over /intelligence/analysis.`,
          },
        ]);
        return;
      }
      const analysis = asRecord(await intelligenceApi.analysis("FX"));
      const sections = [
        "Market conditions:",
        ...asList(analysis.market_conditions).map((l) => `• ${String(l)}`),
        "",
        "Risk factors:",
        ...asList(analysis.risk_factors).map((l) => `• ${String(l)}`),
        "",
        "News impact:",
        ...asList(analysis.news_impact).map((l) => `• ${String(l)}`),
        "",
        "Portfolio exposure:",
        ...asList(analysis.portfolio_exposure).map((l) => `• ${String(l)}`),
        "",
        str(analysis.disclaimer),
      ];
      setMessages((m) => [...m, { role: "assistant", content: sections.join("\n") }]);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Analysis failed");
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content:
            "Unable to load advisory analysis. Connect MT5 / check API auth, then retry. No fabricated insights will be shown.",
        },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <FeatureGate flag="ai" label="AI Assistant">
      <div className="flex h-[calc(100vh-7rem)] flex-col">
        <PageHeader
          title="AI Assistant"
          description="Advisor summaries from real platform data — never autonomous trading."
        />
        <div className="mb-3 flex flex-wrap gap-2">
          {starters.map((s) => (
            <Button key={s} size="sm" variant="secondary" onClick={() => send(s)} disabled={busy}>
              {s}
            </Button>
          ))}
        </div>
        <Card className="flex min-h-0 flex-1 flex-col">
          <CardContent className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-4">
            {messages.map((m, i) => (
              <div
                key={i}
                className={
                  m.role === "user"
                    ? "ml-auto max-w-[80%] rounded-xl bg-[var(--accent)] px-3 py-2 text-sm text-[var(--accent-fg)]"
                    : "mr-auto max-w-[80%] whitespace-pre-wrap rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-sm text-[var(--fg)]"
                }
              >
                {m.content}
              </div>
            ))}
          </CardContent>
          <form
            className="flex gap-2 border-t border-[var(--border)] p-3"
            onSubmit={(e) => {
              e.preventDefault();
              void send(input);
            }}
          >
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about risk, exposure, or market context…"
              aria-label="Message to AI assistant"
              disabled={busy}
            />
            <Button type="submit" disabled={busy}>
              Send
            </Button>
          </form>
        </Card>
      </div>
    </FeatureGate>
  );
}
