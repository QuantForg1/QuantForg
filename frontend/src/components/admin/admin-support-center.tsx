"use client";

import { useState } from "react";
import { LifeBuoy } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskEmpty, DeskError, DeskSkeleton, DeskTable } from "@/components/desk/primitives";
import { NocPanel } from "@/components/ops/noc/noc-primitives";
import { customerOpsApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { useAuth } from "@/providers/auth-provider";
import {
  canAccessIteOps,
  iteOpsAccessDeniedMessage,
} from "@/lib/auth/ite-ops-access";

const STATUS_OPTIONS = [
  "pending",
  "in_progress",
  "resolved",
  "closed",
] as const;

const PRIORITY_OPTIONS = ["low", "normal", "high", "urgent"] as const;

function fmt(v: unknown, fallback = "—"): string {
  if (v === null || v === undefined || v === "") return fallback;
  return String(v);
}

export function AdminSupportCenter() {
  const { user } = useAuth();
  const allowed = canAccessIteOps(user);
  const qc = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [status, setStatus] = useState("pending");
  const [priority, setPriority] = useState("normal");
  const [assignee, setAssignee] = useState("");
  const [note, setNote] = useState("");

  const supportQ = useQuery({
    queryKey: ["customer-ops-support"],
    queryFn: () => customerOpsApi.support(),
    enabled: allowed,
    refetchInterval: 15_000,
    retry: false,
  });

  const updateTicket = useMutation({
    mutationFn: (p: { id: string; body: Record<string, unknown> }) =>
      customerOpsApi.updateTicket(p.id, p.body),
    onSuccess: () => {
      setNote("");
      void qc.invalidateQueries({ queryKey: ["customer-ops-support"] });
      void qc.invalidateQueries({ queryKey: ["customer-ops-platform"] });
    },
  });

  const root = asRecord(supportQ.data);
  const tickets = asList(root.tickets);
  const selected = tickets
    .map(asRecord)
  .find((t) => str(t.id, "") === selectedId);

  if (!allowed) {
    return (
      <DeskError
        message={iteOpsAccessDeniedMessage(user, undefined, "Support Management")}
      />
    );
  }

  if (supportQ.isLoading && !supportQ.data) {
    return <DeskSkeleton rows={10} />;
  }

  if (supportQ.error && !supportQ.data) {
    return (
      <DeskError
        message={iteOpsAccessDeniedMessage(user, supportQ.error, "Support Management")}
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="neutral">Support ops</Badge>
        <Badge tone="warning">{fmt(root.pending_count, "0")} pending</Badge>
        <Badge tone="neutral">{fmt(root.count, "0")} total</Badge>
      </div>

      <NocPanel title="Support tickets">
        {tickets.length === 0 ? (
          <DeskEmpty
            icon={LifeBuoy}
            title="No support tickets"
            description="When customers open requests, they appear here with real status from COP."
          />
        ) : (
          <DeskTable
            columns={["ID", "Subject", "Priority", "Status", "Assigned", ""]}
            rows={tickets.slice(0, 80).map((row) => {
              const r = asRecord(row);
              const id = fmt(r.id);
              return [
                id.slice(0, 12),
                fmt(r.subject),
                fmt(r.priority),
                fmt(r.status),
                fmt(r.assigned_staff, "—"),
                <Button
                  key={`sel-${id}`}
                  type="button"
                  size="sm"
                  variant={selectedId === id ? "secondary" : "outline"}
                  onClick={() => {
                    setSelectedId(id);
                    setStatus(String(r.status || "pending"));
                    setPriority(String(r.priority || "normal"));
                    setAssignee(String(r.assigned_staff || ""));
                    setNote("");
                  }}
                >
                  Manage
                </Button>,
              ];
            })}
          />
        )}
      </NocPanel>

      {selected ? (
        <NocPanel title={`Ticket · ${fmt(selected.subject)}`}>
          <p className="mb-3 text-[12px] text-[var(--fg-muted)]">
            ID {fmt(selected.id)} · customer {fmt(selected.customer_id, "—")}
          </p>
          {selected.body ? (
            <p className="mb-4 rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-[12px] text-[var(--fg)]">
              {fmt(selected.body)}
            </p>
          ) : null}
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <label className="space-y-1 text-[11px] text-[var(--fg-muted)]">
              Status
              <select
                className="w-full border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5 text-[12px] text-[var(--fg)]"
                value={status}
                onChange={(e) => setStatus(e.target.value)}
              >
                {STATUS_OPTIONS.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-1 text-[11px] text-[var(--fg-muted)]">
              Priority
              <select
                className="w-full border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5 text-[12px] text-[var(--fg)]"
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
              >
                {PRIORITY_OPTIONS.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-1 text-[11px] text-[var(--fg-muted)] sm:col-span-2">
              Assigned staff
              <input
                className="w-full border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5 text-[12px]"
                value={assignee}
                onChange={(e) => setAssignee(e.target.value)}
                placeholder="Operator email or name"
              />
            </label>
          </div>
          <label className="mt-3 block space-y-1 text-[11px] text-[var(--fg-muted)]">
            Internal note / reply
            <textarea
              className="min-h-[88px] w-full border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5 text-[12px]"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Add operator note (stored in ticket timeline)"
            />
          </label>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button
              size="sm"
              disabled={updateTicket.isPending}
              onClick={() => {
                const id = str(selected.id, "");
                if (!id) return;
                updateTicket.mutate({
                  id,
                  body: {
                    status,
                    priority,
                    assigned_staff: assignee || null,
                    ...(note.trim() ? { internal_note: note.trim() } : {}),
                  },
                });
              }}
            >
              {updateTicket.isPending ? "Saving…" : "Save changes"}
            </Button>
            {updateTicket.isError ? (
              <span className="text-[12px] text-[var(--danger)]">
                Update failed — check owner session and ticket id.
              </span>
            ) : null}
          </div>
        </NocPanel>
      ) : (
        <p className="text-[12px] text-[var(--fg-muted)]">
          Select a ticket to update status, assignment, or add an internal note.
        </p>
      )}
    </div>
  );
}
