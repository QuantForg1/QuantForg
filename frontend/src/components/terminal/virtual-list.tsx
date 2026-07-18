"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
  type CSSProperties,
} from "react";

/**
 * Lightweight windowed list — no extra dependency.
 * Renders only rows intersecting the viewport (+ overscan).
 */
export function VirtualList<T>({
  items,
  rowHeight,
  overscan = 8,
  className,
  style,
  "aria-label": ariaLabel,
  renderRow,
  empty,
}: {
  items: T[];
  rowHeight: number;
  overscan?: number;
  className?: string;
  style?: CSSProperties;
  "aria-label"?: string;
  renderRow: (item: T, index: number) => ReactNode;
  empty?: ReactNode;
}) {
  const scrollerRef = useRef<HTMLDivElement>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [viewportH, setViewportH] = useState(240);

  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;
    const measure = () => setViewportH(el.clientHeight || 240);
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const onScroll = useCallback(() => {
    const el = scrollerRef.current;
    if (el) setScrollTop(el.scrollTop);
  }, []);

  const total = items.length;
  const { start, end, offsetY } = useMemo(() => {
    const visible = Math.ceil(viewportH / rowHeight) + overscan * 2;
    const startIdx = Math.max(0, Math.floor(scrollTop / rowHeight) - overscan);
    const endIdx = Math.min(total, startIdx + visible);
    return { start: startIdx, end: endIdx, offsetY: startIdx * rowHeight };
  }, [scrollTop, viewportH, rowHeight, overscan, total]);

  if (total === 0) {
    return (
      <div className={className} style={style} role="list" aria-label={ariaLabel}>
        {empty}
      </div>
    );
  }

  const slice = items.slice(start, end);

  return (
    <div
      ref={scrollerRef}
      className={className}
      style={{ overflow: "auto", ...style }}
      onScroll={onScroll}
      role="list"
      aria-label={ariaLabel}
    >
      <div style={{ height: total * rowHeight, position: "relative" }}>
        <div style={{ transform: `translateY(${offsetY}px)` }}>
          {slice.map((item, i) => (
            <div
              key={start + i}
              role="listitem"
              style={{ height: rowHeight }}
              className="box-border"
            >
              {renderRow(item, start + i)}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
