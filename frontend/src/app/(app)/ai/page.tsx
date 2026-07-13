"use client";

import { useState } from "react";
import { toast } from "sonner";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { env } from "@/lib/env";

type Msg = { role: "user" | "assistant"; content: string };

const starters = [
  "Explain my current portfolio risk",
  "Suggest a safer EURUSD position size",
  "Summarize last backtest takeaways",
];

export default function AiPage() {
  const [messages, setMessages] = useState<Msg[]>([
    {
      role: "assistant",
      content: env.useMockAi
        ? "Mock AI is enabled for local UX only. Responses are not from a live model."
        : "AI model gateway is not configured for this deployment. Enable NEXT_PUBLIC_MOCK_AI for local demos, or connect a gateway in a future release — no fabricated insights are returned.",
    },
  ]);
  const [input, setInput] = useState("");

  function send(text: string) {
    if (!text.trim()) return;
    const user: Msg = { role: "user", content: text };
    if (!env.useMockAi) {
      setMessages((m) => [
        ...m,
        user,
        {
          role: "assistant",
          content:
            "No AI provider is configured. QuantForg will not invent trade advice without a connected gateway.",
        },
      ]);
      setInput("");
      toast.message("AI unavailable", {
        description: "Model gateway not configured on this environment.",
      });
      return;
    }
    const reply: Msg = {
      role: "assistant",
      content: `[mock] Received: “${text}”. Wire a real model gateway before beta AI features go live.`,
    };
    setMessages((m) => [...m, user, reply]);
    setInput("");
  }

  return (
    <div className="flex h-[calc(100vh-7rem)] flex-col">
      <PageHeader
        title="AI Assistant"
        description="Market insights, strategy explanation, and portfolio analysis."
      />
      <div className="mb-3 flex flex-wrap gap-2">
        {starters.map((s) => (
          <Button key={s} size="sm" variant="secondary" onClick={() => send(s)}>
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
                  : "mr-auto max-w-[80%] rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-sm text-[var(--fg)]"
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
            send(input);
          }}
        >
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about risk, strategy, or markets…"
            aria-label="Message to AI assistant"
          />
          <Button type="submit">Send</Button>
        </form>
      </Card>
    </div>
  );
}
