"use client";

import Link from "next/link";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

export const PHASE6_MODULES = [
  { href: "/intelligence-center", label: "Hub" },
  { href: "/predictive-market-intelligence", label: "Market" },
  { href: "/strategy-analytics", label: "Strategy" },
  { href: "/predictive-risk", label: "Risk" },
  { href: "/portfolio-optimization", label: "Portfolio" },
  { href: "/execution-optimization", label: "Execution" },
  { href: "/decision-intelligence", label: "Decisions" },
  { href: "/institutional-reports", label: "Reports" },
] as const;

export function Phase6ModuleNav({ current }: { current: string }) {
  return (
    <nav className="mb-4 flex flex-wrap gap-2 border-b border-border/60 pb-3">
      {PHASE6_MODULES.map((m) => (
        <Link
          key={m.href}
          href={m.href}
          className={cn(
            "rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
            current === m.href
              ? "bg-accent/15 text-accent"
              : "text-muted-foreground hover:bg-muted/40 hover:text-foreground",
          )}
        >
          {m.label}
        </Link>
      ))}
    </nav>
  );
}

export function Phase6Banner({
  children,
  tone = "neutral",
}: {
  children: React.ReactNode;
  tone?: "neutral" | "warn" | "ok";
}) {
  return (
    <div
      className={cn(
        "mb-4 rounded-md border px-3 py-2 text-xs leading-relaxed",
        tone === "warn" &&
          "border-amber-500/40 bg-amber-500/5 text-amber-100/90",
        tone === "ok" && "border-accent/30 bg-accent/5 text-foreground/80",
        tone === "neutral" &&
          "border-border/70 bg-muted/20 text-muted-foreground",
      )}
    >
      {children}
    </div>
  );
}

export function Phase6Stat({
  label,
  value,
  hint,
}: {
  label: string;
  value: string | number | null | undefined;
  hint?: string;
}) {
  return (
    <div className="rounded-md border border-border/60 bg-card/40 px-3 py-2">
      <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className="mt-1 font-mono text-sm text-foreground">
        {value === null || value === undefined || value === ""
          ? "—"
          : String(value)}
      </div>
      {hint ? (
        <div className="mt-1 text-[10px] text-muted-foreground">{hint}</div>
      ) : null}
    </div>
  );
}

export function Phase6TabBar<T extends string>({
  tabs,
  value,
  onChange,
}: {
  tabs: { id: T; label: string }[];
  value: T;
  onChange: (id: T) => void;
}) {
  return (
    <div className="mb-3 flex flex-wrap gap-1">
      {tabs.map((t) => (
        <Button
          key={t.id}
          size="sm"
          variant={value === t.id ? "default" : "ghost"}
          className="h-7 text-xs"
          onClick={() => onChange(t.id)}
        >
          {t.label}
        </Button>
      ))}
    </div>
  );
}

export function Phase6Empty({ message }: { message: string }) {
  return (
    <div className="rounded-md border border-dashed border-border/70 px-4 py-8 text-center text-sm text-muted-foreground">
      {message}
    </div>
  );
}

export function Phase6Loading() {
  return (
    <div className="py-8 text-center text-sm text-muted-foreground">
      Loading…
    </div>
  );
}

export function Phase6Error({ message }: { message: string }) {
  return (
    <div className="rounded-md border border-red-500/30 bg-red-500/5 px-3 py-2 text-sm text-red-200">
      {message}
    </div>
  );
}
