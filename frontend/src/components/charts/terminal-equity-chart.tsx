"use client";

import { useId, useRef, useState } from "react";
import {
  Area,
  AreaChart,
  Brush,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Download, Expand, FileSpreadsheet } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";

export function TerminalEquityChart({
  data,
  emptyLabel = "No equity history from synced deals yet",
}: {
  data: { t: string; equity: number }[];
  emptyLabel?: string;
}) {
  const [fullscreen, setFullscreen] = useState(false);
  const chartId = useId().replace(/:/g, "");
  const wrapRef = useRef<HTMLDivElement>(null);

  const exportCsv = () => {
    if (!data.length) {
      toast.message("Nothing to export");
      return;
    }
    const rows = [["time", "equity"], ...data.map((d) => [d.t, String(d.equity)])];
    const blob = new Blob([rows.map((r) => r.join(",")).join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "quantforg-equity-curve.csv";
    a.click();
    URL.revokeObjectURL(url);
    toast.success("Equity CSV exported");
  };

  const exportPng = async () => {
    const svg = wrapRef.current?.querySelector("svg");
    if (!svg) {
      toast.message("Chart not ready");
      return;
    }
    const xml = new XMLSerializer().serializeToString(svg);
    const svgBlob = new Blob([xml], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(svgBlob);
    const img = new Image();
    const w = svg.clientWidth || 800;
    const h = svg.clientHeight || 320;
    await new Promise<void>((resolve, reject) => {
      img.onload = () => resolve();
      img.onerror = () => reject(new Error("png"));
      img.src = url;
    }).catch(() => {
      toast.error("PNG export failed");
      URL.revokeObjectURL(url);
    });
    const canvas = document.createElement("canvas");
    canvas.width = w * 2;
    canvas.height = h * 2;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.fillStyle = "#0f1620";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.scale(2, 2);
    ctx.drawImage(img, 0, 0, w, h);
    URL.revokeObjectURL(url);
    const a = document.createElement("a");
    a.href = canvas.toDataURL("image/png");
    a.download = "quantforg-equity-curve.png";
    a.click();
    toast.success("Equity PNG exported");
  };

  const chart = (height: number) =>
    !data.length ? (
      <div
        className="flex items-center justify-center text-sm text-[var(--fg-subtle)]"
        style={{ height }}
        role="img"
        aria-label={emptyLabel}
      >
        {emptyLabel}
      </div>
    ) : (
      <div ref={wrapRef} style={{ height }} role="img" aria-label="Equity curve">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id={`eq-${chartId}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#2dd4bf" stopOpacity={0.4} />
                <stop offset="100%" stopColor="#2dd4bf" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="t"
              stroke="var(--fg-subtle)"
              fontSize={11}
              tickLine={false}
              axisLine={false}
              minTickGap={28}
            />
            <YAxis
              stroke="var(--fg-subtle)"
              fontSize={11}
              tickLine={false}
              axisLine={false}
              width={56}
              tickFormatter={(v) => `$${(Number(v) / 1000).toFixed(0)}k`}
            />
            <Tooltip
              contentStyle={{
                background: "var(--surface)",
                border: "1px solid var(--border)",
                borderRadius: 10,
                boxShadow: "var(--shadow-card)",
              }}
            />
            <Area
              type="monotone"
              dataKey="equity"
              stroke="#2dd4bf"
              fill={`url(#eq-${chartId})`}
              strokeWidth={2.25}
              animationDuration={900}
              isAnimationActive
            />
            {data.length > 8 ? (
              <Brush
                dataKey="t"
                height={22}
                stroke="var(--accent)"
                fill="var(--surface-2)"
                travellerWidth={8}
              />
            ) : null}
          </AreaChart>
        </ResponsiveContainer>
      </div>
    );

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Badge tone="accent">Synced deals</Badge>
        <div className="flex flex-wrap gap-1.5">
          <Button size="sm" variant="ghost" onClick={exportCsv} aria-label="Export CSV">
            <FileSpreadsheet className="h-3.5 w-3.5" /> CSV
          </Button>
          <Button size="sm" variant="ghost" onClick={exportPng} aria-label="Export PNG">
            <Download className="h-3.5 w-3.5" /> PNG
          </Button>
          <Button
            size="sm"
            variant="secondary"
            onClick={() => setFullscreen(true)}
            aria-label="Fullscreen chart"
          >
            <Expand className="h-3.5 w-3.5" /> Fullscreen
          </Button>
        </div>
      </div>
      {chart(280)}
      <Dialog open={fullscreen} onOpenChange={setFullscreen}>
        <DialogContent className="max-w-[min(96vw,1200px)]">
          <DialogTitle className="mb-3 pr-10">Equity curve</DialogTitle>
          {chart(420)}
        </DialogContent>
      </Dialog>
    </div>
  );
}
