"use client";

import { useCallback, useEffect, useRef } from "react";

/** Drag-to-resize for workspace panels. Returns pointer handlers bound to an axis. */
export function useResizeSplit(onDelta: (deltaPx: number) => void) {
  const dragging = useRef(false);
  const axis = useRef<"x" | "y">("x");

  const start = useCallback((nextAxis: "x" | "y") => {
    return (e: React.PointerEvent) => {
      e.preventDefault();
      axis.current = nextAxis;
      dragging.current = true;
      (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId);
    };
  }, []);

  useEffect(() => {
    const onMove = (e: PointerEvent) => {
      if (!dragging.current) return;
      onDelta(axis.current === "x" ? e.movementX : e.movementY);
    };
    const onUp = () => {
      dragging.current = false;
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, [onDelta]);

  return { start };
}

export function SplitHandle({
  orientation,
  onStartDrag,
  onStep,
  label,
}: {
  orientation: "vertical" | "horizontal";
  onStartDrag: (e: React.PointerEvent) => void;
  onStep: (delta: number) => void;
  label: string;
}) {
  const vertical = orientation === "vertical";
  return (
    <div
      role="separator"
      aria-orientation={orientation}
      aria-label={label}
      tabIndex={0}
      onPointerDown={onStartDrag}
      onKeyDown={(e) => {
        const step = e.shiftKey ? 40 : 16;
        if (vertical && e.key === "ArrowLeft") {
          e.preventDefault();
          onStep(-step);
        } else if (vertical && e.key === "ArrowRight") {
          e.preventDefault();
          onStep(step);
        } else if (!vertical && e.key === "ArrowUp") {
          e.preventDefault();
          onStep(-step);
        } else if (!vertical && e.key === "ArrowDown") {
          e.preventDefault();
          onStep(step);
        }
      }}
      className={
        vertical
          ? "z-10 w-1.5 shrink-0 cursor-col-resize bg-[var(--border)] hover:bg-[var(--accent)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent)]"
          : "z-10 h-1.5 shrink-0 cursor-row-resize bg-[var(--border)] hover:bg-[var(--accent)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent)]"
      }
    />
  );
}
