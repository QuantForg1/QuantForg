"use client";

import { Keyboard } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DeskTable } from "@/components/desk/primitives";
import { PageMotion } from "@/components/desk/motion";

const GLOBAL_SHORTCUTS: [string, string][] = [
  ["⌘1 / Ctrl+1", "Terminal"],
  ["⌘2 / Ctrl+2", "Portfolio"],
  ["⌘3 / Ctrl+3", "Research"],
  ["⌘4 / Ctrl+4", "Journal"],
  ["⌘5 / Ctrl+5", "Broker"],
  ["⌘6 / Ctrl+6", "Monitoring"],
];

const TERMINAL_SHORTCUTS: [string, string][] = [
  ["B / S", "Buy / Sell (confirm)"],
  ["1–3", "Blotter tabs"],
  ["]", "Toggle order ticket"],
  ["\\", "Toggle blotter"],
  ["C", "Toggle AI decision"],
  ["F", "Chart fullscreen"],
  ["Esc", "Cancel / close sheets"],
  ["?", "Keyboard help"],
];

const PORTFOLIO_SHORTCUTS: [string, string][] = [
  ["1", "Focus Portfolio Health"],
  ["2", "Focus Equity Timeline"],
  ["3", "Focus Risk DNA"],
  ["4", "Focus Exposure Map"],
  ["5", "Focus Position Intelligence"],
  ["C", "Toggle Portfolio Counsel"],
  ["R", "Refresh book data"],
  ["?", "Keyboard help"],
];

function ShortcutTable({ rows }: { rows: [string, string][] }) {
  return (
    <DeskTable
      columns={["Shortcut", "Action"]}
      rows={rows.map(([keys, action]) => [
        <kbd
          key={keys}
          className="rounded border border-[var(--border)] bg-[var(--surface-2)] px-1.5 py-0.5 font-mono text-[11px]"
        >
          {keys}
        </kbd>,
        action,
      ])}
    />
  );
}

export default function ShortcutsPage() {
  return (
    <div>
      <PageHeader
        title="Keyboard Shortcuts"
        description="Global OS navigation and desk-specific bindings. Shortcuts are suppressed while typing in inputs."
      />
      <PageMotion className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Keyboard className="h-4 w-4 text-[var(--accent)]" />
              Global OS
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ShortcutTable rows={GLOBAL_SHORTCUTS} />
          </CardContent>
        </Card>
        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Terminal</CardTitle>
            </CardHeader>
            <CardContent>
              <ShortcutTable rows={TERMINAL_SHORTCUTS} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Portfolio</CardTitle>
            </CardHeader>
            <CardContent>
              <ShortcutTable rows={PORTFOLIO_SHORTCUTS} />
            </CardContent>
          </Card>
        </div>
      </PageMotion>
    </div>
  );
}
