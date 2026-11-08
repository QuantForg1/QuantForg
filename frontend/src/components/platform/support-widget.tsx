"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Headphones, LifeBuoy, MessageSquare, Ticket, X } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { supportDeskApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";

type Panel = "menu" | "chat" | "ticket" | "tickets" | "thread";

export function SupportWidget() {
  const pathname = usePathname();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [panel, setPanel] = useState<Panel>("menu");
  const [aiSessionId, setAiSessionId] = useState<string | undefined>();
  const [chatInput, setChatInput] = useState("");
  const [chatLog, setChatLog] = useState<{ role: "user" | "assistant"; text: string }[]>([]);
  const [ticketSubject, setTicketSubject] = useState("");
  const [ticketBody, setTicketBody] = useState("");
  const [ticketCategory, setTicketCategory] = useState("general");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [reply, setReply] = useState("");

  /** Floating widget is Support-desk only — never on trader desks or /admin. */
  const onSupportDesk = useMemo(() => {
    if (!pathname) return false;
    return pathname === "/support" || pathname.startsWith("/support/");
  }, [pathname]);

  const faq = useQuery({
    queryKey: ["support-desk", "faq"],
    queryFn: supportDeskApi.faq,
    enabled: onSupportDesk && open,
    staleTime: 60_000,
  });

  const ticketsQ = useQuery({
    queryKey: ["support-desk", "tickets"],
    queryFn: supportDeskApi.tickets,
    enabled:
      onSupportDesk &&
      open &&
      (panel === "tickets" || panel === "thread" || panel === "menu"),
  });

  const threadQ = useQuery({
    queryKey: ["support-desk", "ticket", selectedId],
    queryFn: () => supportDeskApi.ticket(selectedId!),
    enabled: onSupportDesk && open && panel === "thread" && !!selectedId,
  });

  const chatMut = useMutation({
    mutationFn: (message: string) => supportDeskApi.aiChat(message, aiSessionId),
    onSuccess: (data) => {
      const sid = str(data.ai_session_id);
      if (sid) setAiSessionId(sid);
      const answer = str(data.answer);
      setChatLog((prev) => [...prev, { role: "assistant", text: answer }]);
    },
    onError: () => toast.error("Unable to reach support assistant"),
  });

  const createMut = useMutation({
    mutationFn: () =>
      supportDeskApi.createTicket({
        subject: ticketSubject,
        body: ticketBody,
        category: ticketCategory,
        ai_session_id: aiSessionId,
      }),
    onSuccess: (data) => {
      toast.success("Ticket created");
      setTicketSubject("");
      setTicketBody("");
      void qc.invalidateQueries({ queryKey: ["support-desk", "tickets"] });
      const id = str(data.id);
      if (id) {
        setSelectedId(id);
        setPanel("thread");
      } else {
        setPanel("tickets");
      }
    },
    onError: () => toast.error("Unable to create ticket"),
  });

  const messageMut = useMutation({
    mutationFn: () => supportDeskApi.postMessage(selectedId!, reply),
    onSuccess: () => {
      setReply("");
      void qc.invalidateQueries({ queryKey: ["support-desk", "ticket", selectedId] });
      void qc.invalidateQueries({ queryKey: ["support-desk", "tickets"] });
    },
    onError: () => toast.error("Unable to send message"),
  });

  const humanMut = useMutation({
    mutationFn: () => supportDeskApi.requestHuman(selectedId!),
    onSuccess: () => {
      toast.success("Human agent requested");
      void qc.invalidateQueries({ queryKey: ["support-desk", "ticket", selectedId] });
    },
    onError: () => toast.error("Unable to request human agent"),
  });

  const tickets = asList(ticketsQ.data?.tickets).map(asRecord);
  const thread = asRecord(threadQ.data);
  const messages = asList(thread.messages).map(asRecord);
  const humanConnected = thread.human_agent_connected === true;
  const suggested = asList(faq.data?.suggested_questions).map((x) => str(x));

  if (!onSupportDesk) {
    return null;
  }

  return (
    <div className="fixed bottom-4 right-4 z-40 flex flex-col items-end gap-2 pointer-events-none">
      {open ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Support center"
          className="pointer-events-auto w-[min(92vw,24rem)] max-h-[min(70vh,32rem)] overflow-hidden rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] shadow-[var(--shadow-card)] flex flex-col"
        >
          <div className="flex items-center justify-between border-b border-[var(--border)] px-3 py-2">
            <p className="text-sm font-semibold text-[var(--fg)] flex items-center gap-2">
              <LifeBuoy className="h-4 w-4 text-[var(--accent)]" aria-hidden />
              Support
            </p>
            <div className="flex items-center gap-1">
              {panel !== "menu" ? (
                <Button size="sm" variant="ghost" onClick={() => setPanel("menu")}>
                  Back
                </Button>
              ) : null}
              <Button size="icon" variant="ghost" aria-label="Close support" onClick={() => setOpen(false)}>
                <X className="h-4 w-4" />
              </Button>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-3 text-sm">
            {panel === "menu" ? (
              <div className="space-y-2">
                <p className="text-[var(--fg-muted)]">
                  Platform help, tickets, and escalation — no trading actions from this assistant.
                </p>
                <Button className="w-full justify-start" variant="secondary" onClick={() => setPanel("chat")}>
                  <MessageSquare className="h-4 w-4" /> Ask support AI
                </Button>
                <Button className="w-full justify-start" variant="secondary" onClick={() => setPanel("ticket")}>
                  <Ticket className="h-4 w-4" /> New ticket
                </Button>
                <Button className="w-full justify-start" variant="secondary" onClick={() => setPanel("tickets")}>
                  <Headphones className="h-4 w-4" /> My tickets
                  {tickets.length > 0 ? (
                    <Badge tone="neutral" className="ml-auto">
                      {tickets.length}
                    </Badge>
                  ) : null}
                </Button>
                <Button size="sm" variant="ghost" asChild className="w-full">
                  <Link href="/support">Open full Support desk</Link>
                </Button>
              </div>
            ) : null}

            {panel === "chat" ? (
              <div className="space-y-3">
                <div className="max-h-48 space-y-2 overflow-y-auto rounded-md border border-[var(--border)] p-2">
                  {chatLog.length === 0 ? (
                    <p className="text-xs text-[var(--fg-muted)]">
                      Verified FAQ answers only. Unsure topics should become a ticket.
                    </p>
                  ) : (
                    chatLog.map((m, i) => (
                      <p
                        key={`${i}-${m.role}`}
                        className={
                          m.role === "user"
                            ? "text-[var(--fg)]"
                            : "text-[var(--fg-muted)] border-l-2 border-[var(--accent)] pl-2"
                        }
                      >
                        {m.text}
                      </p>
                    ))
                  )}
                </div>
                {suggested.length > 0 ? (
                  <div className="flex flex-wrap gap-1">
                    {suggested.map((q) => (
                      <button
                        key={q}
                        type="button"
                        className="rounded-full border border-[var(--border)] px-2 py-0.5 text-xs text-[var(--fg-muted)] hover:border-[var(--accent)]"
                        onClick={() => {
                          setChatInput(q);
                          setChatLog((prev) => [...prev, { role: "user", text: q }]);
                          chatMut.mutate(q);
                        }}
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                ) : null}
                <form
                  className="flex gap-2"
                  onSubmit={(e) => {
                    e.preventDefault();
                    const msg = chatInput.trim();
                    if (!msg) return;
                    setChatLog((prev) => [...prev, { role: "user", text: msg }]);
                    setChatInput("");
                    chatMut.mutate(msg);
                  }}
                >
                  <Input
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    placeholder="Ask a platform question…"
                    aria-label="Support question"
                  />
                  <Button type="submit" size="sm" disabled={chatMut.isPending}>
                    Send
                  </Button>
                </form>
              </div>
            ) : null}

            {panel === "ticket" ? (
              <form
                className="space-y-3"
                onSubmit={(e) => {
                  e.preventDefault();
                  if (!ticketSubject.trim() || !ticketBody.trim()) {
                    toast.error("Subject and message required");
                    return;
                  }
                  createMut.mutate();
                }}
              >
                <div className="space-y-1">
                  <Label htmlFor="sw-cat">Category</Label>
                  <select
                    id="sw-cat"
                    className="flex h-9 w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 text-sm"
                    value={ticketCategory}
                    onChange={(e) => setTicketCategory(e.target.value)}
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
                  <Label htmlFor="sw-subject">Subject</Label>
                  <Input
                    id="sw-subject"
                    value={ticketSubject}
                    onChange={(e) => setTicketSubject(e.target.value)}
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="sw-body">Message</Label>
                  <textarea
                    id="sw-body"
                    className="min-h-24 w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 py-1.5 text-sm"
                    value={ticketBody}
                    onChange={(e) => setTicketBody(e.target.value)}
                  />
                </div>
                <Button type="submit" className="w-full" disabled={createMut.isPending}>
                  Submit ticket
                </Button>
              </form>
            ) : null}

            {panel === "tickets" ? (
              <ul className="space-y-2">
                {ticketsQ.isLoading ? (
                  <p className="text-[var(--fg-muted)]">Loading…</p>
                ) : tickets.length === 0 ? (
                  <p className="text-[var(--fg-muted)]">No tickets yet.</p>
                ) : (
                  tickets.map((t) => (
                    <li key={str(t.id)}>
                      <button
                        type="button"
                        className="w-full rounded-md border border-[var(--border)] px-2 py-2 text-left hover:border-[var(--accent)]"
                        onClick={() => {
                          setSelectedId(str(t.id));
                          setPanel("thread");
                        }}
                      >
                        <p className="font-medium text-[var(--fg)]">{str(t.subject)}</p>
                        <p className="text-xs text-[var(--fg-muted)]">
                          {str(t.status)} · {str(t.updated_at)}
                        </p>
                      </button>
                    </li>
                  ))
                )}
              </ul>
            ) : null}

            {panel === "thread" && selectedId ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <p className="font-medium">{str(thread.subject)}</p>
                  <Badge tone="neutral">{str(thread.status)}</Badge>
                </div>
                {humanConnected ? (
                  <p className="text-xs text-[var(--accent)]">Human agent connected</p>
                ) : thread.human_requested === true ? (
                  <p className="text-xs text-[var(--fg-muted)]">Awaiting human agent acceptance</p>
                ) : null}
                <ul className="max-h-40 space-y-2 overflow-y-auto">
                  {messages.map((m) => (
                    <li
                      key={str(m.id)}
                      className="rounded-md border border-[var(--border)] px-2 py-1.5 text-xs"
                    >
                      <span className="text-[var(--fg-subtle)]">{str(m.role)} · </span>
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
                    placeholder="Reply…"
                    aria-label="Ticket reply"
                  />
                  <Button type="submit" size="sm" disabled={messageMut.isPending}>
                    Send
                  </Button>
                </form>
                {!humanConnected ? (
                  <Button
                    size="sm"
                    variant="secondary"
                    className="w-full"
                    disabled={humanMut.isPending}
                    onClick={() => humanMut.mutate()}
                  >
                    Request human agent
                  </Button>
                ) : null}
              </div>
            ) : null}
          </div>
        </div>
      ) : null}

      <Button
        size="icon"
        className="pointer-events-auto h-12 w-12 rounded-full shadow-[var(--shadow-card)]"
        aria-label="Open support"
        onClick={() => setOpen((v) => !v)}
      >
        <LifeBuoy className="h-5 w-5" />
      </Button>
    </div>
  );
}
