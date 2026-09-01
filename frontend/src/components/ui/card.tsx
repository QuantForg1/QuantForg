import * as React from "react";
import { cn } from "@/lib/utils";

/** Institutional card — white surface, quiet elevation, token borders. */
export function Card({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] shadow-[var(--shadow-card)] transition-[border-color,box-shadow] duration-[var(--duration-os)] ease-[var(--ease-os)]",
        className,
      )}
      {...props}
    />
  );
}

export function CardHeader({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "flex flex-col gap-1.5 border-b border-[var(--border)] px-[var(--space-4)] py-[var(--space-3)]",
        className,
      )}
      {...props}
    />
  );
}

export function CardTitle({
  className,
  ...props
}: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3
      className={cn(
        "text-sm font-semibold tracking-tight text-[var(--fg)]",
        className,
      )}
      {...props}
    />
  );
}

export function CardDescription({
  className,
  ...props
}: React.HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p className={cn("qf-caption", className)} {...props} />
  );
}

export function CardContent({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("p-[var(--space-4)]", className)}
      {...props}
    />
  );
}
