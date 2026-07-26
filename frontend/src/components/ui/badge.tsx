import { cn } from "@/lib/utils";

export function Badge({
  className,
  tone = "neutral",
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & {
  tone?: "neutral" | "success" | "warning" | "danger" | "accent";
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-[var(--radius-sm)] px-2 py-0.5 text-[11px] font-medium tracking-tight",
        tone === "neutral" && "bg-[var(--surface-2)] text-[var(--fg-muted)]",
        tone === "success" && "bg-[var(--success-soft)] text-[var(--success)]",
        tone === "warning" && "bg-[var(--warning-soft)] text-[var(--warning)]",
        tone === "danger" && "bg-[var(--danger-soft)] text-[var(--danger)]",
        tone === "accent" && "bg-[var(--accent-soft)] text-[var(--accent)]",
        className,
      )}
      {...props}
    />
  );
}
