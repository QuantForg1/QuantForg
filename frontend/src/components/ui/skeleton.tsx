import { cn } from "@/lib/utils";

export function Skeleton({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("qf-shimmer rounded-md", className)}
      aria-hidden
      {...props}
    />
  );
}
