"use client";

import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * Lightweight scroll reveal for marketing surfaces.
 * Respects prefers-reduced-motion; no layout shift (opacity/transform only).
 */
export function Reveal({
  children,
  className,
  delayMs = 0,
}: {
  children: ReactNode;
  className?: string;
  delayMs?: number;
}) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) {
      setVisible(true);
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.08 },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const style = delayMs
    ? ({ ["--qf-reveal-delay" as string]: `${delayMs}ms` } as CSSProperties)
    : undefined;

  return (
    <div
      ref={ref}
      className={cn("qf-reveal", visible && "qf-reveal-visible", className)}
      style={style}
    >
      {children}
    </div>
  );
}
