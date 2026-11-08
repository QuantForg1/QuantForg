"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  BookOpen,
  ChevronDown,
  Headphones,
  HeartPulse,
  LifeBuoy,
  MessageSquare,
  Ticket,
} from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { platformApi, supportDeskApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { toast } from "sonner";

type Section = "overview" | "faq" | "tickets" | "create";

function FaqAccordion({
  items,
}: {
  items: { question: string; answer: string }[];
}) {
  const [open, setOpen] = useState<number | null>(0);
  return (
    <div className="divide-y divide-[var(--border)] overflow-hidden rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)]">
      {items.map((item, index) => {
        const expanded = open === index;
        return (
          <div key={item.question}>
            <button
              type="button"
              className="flex w-full items-center justify-between gap-4 px-4 py-4 text-left text-sm font-medium text-[var(--fg)]"
              aria-expanded={expanded}
              onClick={() => setOpen(expanded ? null : index)}
            >
              {item.question}
              <ChevronDown
                className={`h-4 w-4 shrink-0 text-[var(--fg-muted)] transition-transform ${expanded ? "rotate-180" : ""}`}
              />
            </button>
            {expanded ? (
              <p className="px-4 pb-4 text-sm leading-relaxed text-[var(--fg-muted)]">{item.answer}</p>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

export default function SupportPage() {
  const qc = useQueryClient();
  const [section, setSection] = useState<Section>("overview");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [aiSessionId, setAiSessionId] = useState<string | undefined>();
  const [chatInput, setChatInput] = useState("");
  const [chatLog, setChatLog] = useState<{ role: "user" | "assistant"; text: string }[]>([]);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [category, setCategory] = useState("general");
  const [reply, setReply] = useState("");

  const health = useQuery({
    queryKey: ["health"],
    queryFn: platformApi.health,
    retry: false,
  });
  const version = useQuery({
    queryKey: ["version"],
    queryFn: platformApi.version,
  });
  const faq = useQuery({
    queryKey: ["support-desk", "faq"],
    queryFn: supportDeskApi.faq,
  });
  const ticketsQ = useQuery({
    queryKey: ["support-desk", "tickets"],
    queryFn: supportDeskApi.tickets,
  });
  const threadQ = useQuery({
    queryKey: ["support-desk", "ticket", selectedId],
    queryFn: () => supportDeskApi.ticket(selectedId!),
    enabled: !!selectedId,
  });

  const chatMut = useMutation({
    mutationFn: (message: string) => supportDeskApi.aiChat(message, aiSessionId),
    onSuccess: (data) => {
      const sid = str(data.ai_session_id);
      if (sid) setAiSessionId(sid);
      setChatLog((prev) => [...prev, { role: "assistant", text: str(data.answer) }]);
    },
  });

  const createMut = useMutation({
    mutationFn: () =>
      supportDeskApi.createTicket({ subject, body, category, ai_session_id: aiSessionId }),
    onSuccess: (data) => {
      toast.success("Ticket created");
      setSubject("");
      setBody("");
      void qc.invalidateQueries({ queryKey: ["support-desk", "tickets"] });
      setSelectedId(str(data.id) || null);
      setSection("tickets");
    },
    onError: () => toast.error("Unable to create ticket"),
  });

  const messageMut = useMutation({
    mutationFn: () => supportDeskApi.postMessage(selectedId!, reply),
    onSuccess: () => {
      setReply("");
      void qc.invalidateQueries({ queryKey: ["support-desk", "ticket", selectedId] });
    },
  });

  const humanMut = useMutation({
    mutationFn: () => supportDeskApi.requestHuman(selectedId!),
    onSuccess: () => {
      toast.success("Human agent requested");
      void qc.invalidateQueries({ queryKey: ["support-desk", "ticket", selectedId] });
    },
  });

  const deps = asList(health.data?.dependencies).map(asRecord);
  const status = str(health.data?.status, "unknown");
  const healthy = status === "healthy" || status === "alive";

  const faqItems = useMemo(
    () =>
      asList(faq.data?.items).map((row) => {
        const r = asRecord(row);
        return { question: str(r.question), answer: str(r.answer) };
      }),
    [faq.data],
  );

  const tickets = asList(ticketsQ.data?.tickets).map(asRecord);
  const thread = asRecord(threadQ.data);
  const messages = asList(thread.messages).map(asRecord);
  const humanConnected = thread.human_agent_connected === true;

  const navBtn = (id: Section, label: string) => (
    <Button
      key={id}
      size="sm"
      variant={section === id ? "default" : "secondary"}
      onClick={() => setSection(id)}
    >
      {label}
    </Button>
  );

  return (
    <div>
      <PageHeader
        title="Support"
        description="System status, verified FAQ, tickets, and escalation — trading actions are not available here."
        actions={
          <Button size="sm" variant="secondary" onClick={() => setSection("create")}>
            <Ticket className="h-3.5 w-3.5" /> New ticket
          </Button>
        }
      />

      <div className="mb-4 flex flex-wrap gap-2">
        {navBtn("overview", "Overview")}
        {navBtn("faq", "FAQ")}
        {navBtn("tickets", "My tickets")}
        {navBtn("create", "Create")}
      </div>

      {health.isLoading && section === "overview" ? (
        <DeskSkeleton rows={3} />
      ) : health.isError && section === "overview" ? (
        <DeskError message="Unable to load platform health." onRetry={() => health.refetch()} />
      ) : (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
          {section === "overview" ? (
            <>
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <Card>
                  <CardHeader className="flex-row items-center justify-between">
                    <CardTitle className="flex items-center gap-2 text-base">
                      <HeartPulse className="h-4 w-4 text-[var(--accent)]" /> System status
                    </CardTitle>
                    <Badge tone={healthy ? "success" : "warning"}>{status}</Badge>
                  </CardHeader>
                  <CardContent className="text-sm text-[var(--fg-muted)]">
                    API {str(version.data?.version, "…")} · {str(health.data?.environment, "env")}
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-base">
                      <BookOpen className="h-4 w-4 text-[var(--accent)]" /> Documentation
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2 text-sm text-[var(--fg-muted)]">
                    <p>Desks cover portfolio, risk, paper, and MT5. Contracts remain under /api/v1.</p>
                    <Button size="sm" variant="secondary" asChild>
                      <Link href="/get-started">Onboarding guide</Link>
                    </Button>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-base">
                      <LifeBuoy className="h-4 w-4 text-[var(--accent)]" /> Support widget
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="text-sm text-[var(--fg-muted)]">
                    Use the floating control (bottom-right) for quick FAQ chat and tickets. Hidden on
                    compact Terminal to avoid blocking execution chrome.
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-base">
                      <Headphones className="h-4 w-4 text-[var(--accent)]" /> Operations
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <Button size="sm" variant="secondary" asChild>
                      <Link href="/ops">Open operations</Link>
                    </Button>
                  </CardContent>
                </Card>
              </div>

              <Card>
                <CardHeader>
                  <CardTitle>Dependency health</CardTitle>
                </CardHeader>
                <CardContent>
                  {deps.length === 0 ? (
                    <p className="text-sm text-[var(--fg-muted)]">
                      No dependency incidents in the latest probe.
                    </p>
                  ) : (
                    <ul className="space-y-2">
                      {deps.map((d) => (
                        <li
                          key={str(d.name)}
                          className="flex items-center justify-between rounded-[var(--radius-os)] border border-[var(--border)] px-3 py-2"
                        >
                          <span className="text-sm">{str(d.name)}</span>
                          <Badge
                            tone={
                              str(d.status) === "healthy"
                                ? "success"
                                : str(d.status) === "disabled"
                                  ? "neutral"
                                  : "warning"
                            }
                          >
                            {str(d.status)}
                          </Badge>
                        </li>
                      ))}
                    </ul>
                  )}
                  <p className="mt-4 text-xs text-[var(--fg-subtle)]">
                    Live trading remains gated by EXECUTION_ENABLED.
                  </p>
                </CardContent>
              </Card>
            </>
          ) : null}

          {section === "faq" ? (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <MessageSquare className="h-4 w-4 text-[var(--accent)]" /> FAQ & assistant
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {faq.isLoading ? (
                  <DeskSkeleton rows={2} />
                ) : (
                  <FaqAccordion items={faqItems} />
                )}
                <div className="rounded-[var(--radius-os)] border border-[var(--border)] p-3">
                  <p className="mb-2 text-xs text-[var(--fg-muted)]">
                    Assistant uses verified help text only — it cannot trade or change settings.
                  </p>
                  <div className="mb-2 max-h-32 space-y-1 overflow-y-auto text-sm">
                    {chatLog.map((m, i) => (
                      <p key={i} className={m.role === "user" ? "" : "text-[var(--fg-muted)]"}>
                        {m.text}
                      </p>
                    ))}
                  </div>
                  <form
                    className="flex gap-2"
                    onSubmit={(e) => {
                      e.preventDefault();
                      const msg = chatInput.trim();
                      if (!msg) return;
                      setChatLog((p) => [...p, { role: "user", text: msg }]);
                      setChatInput("");
                      chatMut.mutate(msg);
                    }}
                  >
                    <Input
                      value={chatInput}
                      onChange={(e) => setChatInput(e.target.value)}
                      placeholder="Ask a platform question…"
                    />
                    <Button type="submit" size="sm" disabled={chatMut.isPending}>
                      Ask
                    </Button>
                  </form>
                </div>
              </CardContent>
            </Card>
          ) : null}

          {section === "tickets" ? (
            <div className="grid gap-4 lg:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle>My tickets</CardTitle>
                </CardHeader>
                <CardContent>
                  {ticketsQ.isLoading ? (
                    <DeskSkeleton rows={2} />
                  ) : tickets.length === 0 ? (
                    <p className="text-sm text-[var(--fg-muted)]">No tickets yet.</p>
                  ) : (
                    <ul className="space-y-2">
                      {tickets.map((t) => (
                        <li key={str(t.id)}>
                          <button
                            type="button"
                            className={`w-full rounded-md border px-3 py-2 text-left text-sm ${
                              selectedId === str(t.id)
                                ? "border-[var(--accent)]"
                                : "border-[var(--border)]"
                            }`}
                            onClick={() => setSelectedId(str(t.id))}
                          >
                            <span className="font-medium">{str(t.subject)}</span>
                            <span className="ml-2 text-xs text-[var(--fg-muted)]">{str(t.status)}</span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="flex-row items-center justify-between">
                  <CardTitle>Conversation</CardTitle>
                  {selectedId ? <Badge tone="neutral">{str(thread.status)}</Badge> : null}
                </CardHeader>
                <CardContent className="space-y-3">
                  {!selectedId ? (
                    <p className="text-sm text-[var(--fg-muted)]">Select a ticket to view messages.</p>
                  ) : threadQ.isLoading ? (
                    <DeskSkeleton rows={2} />
                  ) : (
                    <>
                      {humanConnected ? (
                        <p className="text-xs text-[var(--accent)]">Human agent connected</p>
                      ) : thread.human_requested === true ? (
                        <p className="text-xs text-[var(--fg-muted)]">Awaiting human agent acceptance</p>
                      ) : null}
                      <ul className="max-h-64 space-y-2 overflow-y-auto">
                        {messages.map((m) => (
                          <li
                            key={str(m.id)}
                            className="rounded-md border border-[var(--border)] px-2 py-1.5 text-sm"
                          >
                            <span className="text-xs text-[var(--fg-subtle)]">{str(m.role)} · </span>
                            {str(m.body)}
                          </li>
                        ))}
                      </ul>
                      <form
                        className="flex gap-2"
                        onSubmit={(e) => {
                          e.preventDefault();
                          if (!reply.trim()) return;
                          messageMut.mutate();
                        }}
                      >
                        <Input
                          value={reply}
                          onChange={(e) => setReply(e.target.value)}
                          placeholder="Reply to support…"
                        />
                        <Button type="submit" size="sm" disabled={messageMut.isPending}>
                          Send
                        </Button>
                      </form>
                      {!humanConnected ? (
                        <Button
                          size="sm"
                          variant="secondary"
                          disabled={humanMut.isPending}
                          onClick={() => humanMut.mutate()}
                        >
                          Request human agent
                        </Button>
                      ) : null}
                    </>
                  )}
                </CardContent>
              </Card>
            </div>
          ) : null}

          {section === "create" ? (
            <Card>
              <CardHeader>
                <CardTitle>Create ticket</CardTitle>
              </CardHeader>
              <CardContent>
                <form
                  className="max-w-lg space-y-3"
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (!subject.trim() || !body.trim()) {
                      toast.error("Subject and message required");
                      return;
                    }
                    createMut.mutate();
                  }}
                >
                  <div className="space-y-1">
                    <Label htmlFor="cat">Category</Label>
                    <select
                      id="cat"
                      className="flex h-9 w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 text-sm"
                      value={category}
                      onChange={(e) => setCategory(e.target.value)}
                    >
                      {["general", "billing", "broker", "mt5", "technical", "account", "feedback"].map(
                        (c) => (
                          <option key={c} value={c}>
                            {c}
                          </option>
                        ),
                      )}
                    </select>
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="subj">Subject</Label>
                    <Input id="subj" value={subject} onChange={(e) => setSubject(e.target.value)} />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="bdy">Message</Label>
                    <textarea
                      id="bdy"
                      className="min-h-28 w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 py-1.5 text-sm"
                      value={body}
                      onChange={(e) => setBody(e.target.value)}
                    />
                  </div>
                  <Button type="submit" disabled={createMut.isPending}>
                    Submit
                  </Button>
                </form>
              </CardContent>
            </Card>
          ) : null}
        </motion.div>
      )}
    </div>
  );
}
