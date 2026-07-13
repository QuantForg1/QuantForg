"use client";

import { useMemo, useState } from "react";
import { usePathname } from "next/navigation";
import { MessageSquarePlus, X } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { submitFeedback, type FeedbackCategory } from "@/lib/platform/feedback";

export function FeedbackWidget() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [category, setCategory] = useState<FeedbackCategory>("bug");
  const [message, setMessage] = useState("");
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);

  const hidden = useMemo(() => {
    if (process.env.NEXT_PUBLIC_FEEDBACK_DISABLED === "true") return true;
    if (!pathname) return false;
    return (
      pathname.startsWith("/login") ||
      pathname.startsWith("/register") ||
      pathname.startsWith("/forgot-password")
    );
  }, [pathname]);

  if (hidden) return null;

  return (
    <div className="fixed bottom-4 right-4 z-40 flex flex-col items-end gap-2">
      {open ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Send feedback"
          className="w-[min(92vw,22rem)] rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4 shadow-[var(--shadow-card)]"
        >
          <div className="mb-3 flex items-center justify-between">
            <p className="text-sm font-semibold text-[var(--fg)]">Send feedback</p>
            <Button
              size="icon"
              variant="ghost"
              aria-label="Close feedback"
              onClick={() => setOpen(false)}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
          <form
            className="space-y-3"
            onSubmit={(e) => {
              e.preventDefault();
              if (!message.trim()) {
                toast.error("Please enter a message");
                return;
              }
              setBusy(true);
              void submitFeedback({ category, message, email: email || undefined })
                .then(() => {
                  toast.success("Feedback recorded");
                  setMessage("");
                  setOpen(false);
                })
                .catch(() => toast.error("Unable to save feedback"))
                .finally(() => setBusy(false));
            }}
          >
            <div className="space-y-1.5">
              <Label htmlFor="fb-cat">Category</Label>
              <select
                id="fb-cat"
                className="flex h-9 w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 text-sm"
                value={category}
                onChange={(e) => setCategory(e.target.value as FeedbackCategory)}
              >
                <option value="bug">Bug report</option>
                <option value="feature">Feature request</option>
                <option value="general">General feedback</option>
              </select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="fb-msg">Message</Label>
              <textarea
                id="fb-msg"
                className="min-h-24 w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--fg)]"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                required
                maxLength={4000}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="fb-email">Email (optional)</Label>
              <Input
                id="fb-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
              />
            </div>
            <p className="text-[11px] text-[var(--fg-muted)]">
              Browser and build version are attached automatically. Secrets are never collected.
            </p>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="secondary" size="sm" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" size="sm" disabled={busy}>
                Submit
              </Button>
            </div>
          </form>
        </div>
      ) : null}
      <Button
        size="sm"
        className="shadow-lg"
        aria-label="Open feedback"
        onClick={() => setOpen((v) => !v)}
      >
        <MessageSquarePlus className="h-4 w-4" />
        Feedback
      </Button>
    </div>
  );
}
