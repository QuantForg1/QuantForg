"use client";

import * as React from "react";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import { cn } from "@/lib/utils";

export const TooltipProvider = TooltipPrimitive.Provider;
export const Tooltip = TooltipPrimitive.Root;
export const TooltipTrigger = TooltipPrimitive.Trigger;

export function TooltipContent({
  className,
  sideOffset = 6,
  ...props
}: React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>) {
  return (
    <TooltipPrimitive.Portal>
      <TooltipPrimitive.Content
        sideOffset={sideOffset}
        className={cn(
          "z-50 max-w-xs rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--bg-elevated)] px-2.5 py-1.5 text-[11px] leading-snug text-[var(--fg)] shadow-[var(--shadow-elevated)] qf-motion-slide-down",
          className,
        )}
        {...props}
      />
    </TooltipPrimitive.Portal>
  );
}
