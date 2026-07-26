import { cn } from "@/lib/utils";

export function Skeleton({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "qf-shimmer rounded-[var(--radius-sm)] bg-[var(--surface-2)]",
        className,
      )}
      aria-hidden
      {...props}
    />
  );
}
