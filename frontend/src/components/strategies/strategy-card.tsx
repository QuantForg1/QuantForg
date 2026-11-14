"use client";

import { createElement } from "react";
import type { LucideIcon } from "lucide-react";
import { strategyIconForKey } from "@/components/strategies/strategy-icons";
import { asRecord, str } from "@/lib/desk";

type StrategyCardProps = {
  strategyKey: string;
  name: string;
  category: string;
  selected: boolean;
  onSelect: () => void;
  icon?: LucideIcon;
};

export function StrategyCard({
  strategyKey,
  name,
  category,
  selected,
  onSelect,
  icon,
}: StrategyCardProps) {
  const iconType = icon ?? strategyIconForKey(strategyKey);
  return (
    <li>
      <button
        type="button"
        className={`flex h-full w-full flex-col rounded-[var(--radius-os)] border px-3 py-3 text-left transition ${
          selected
            ? "border-[var(--accent)] bg-[var(--accent-soft)] shadow-[0_0_0_1px_color-mix(in_srgb,var(--accent)_42%,transparent)]"
            : "border-[var(--border)] bg-[color-mix(in_srgb,var(--surface)_92%,transparent)] hover:border-[var(--accent)]/35"
        }`}
        onClick={onSelect}
        aria-pressed={selected}
      >
        <span
          className={`mb-3 inline-flex h-10 w-10 items-center justify-center rounded-xl ${
            selected
              ? "bg-[var(--accent)] text-[var(--accent-fg)]"
              : "bg-[var(--accent-soft)] text-[var(--accent)]"
          }`}
        >
          {createElement(iconType, { className: "h-4 w-4", "aria-hidden": true })}
        </span>
        <span className="text-sm font-semibold text-[var(--fg)]">{name}</span>
        <span className="mt-1 text-xs text-[var(--fg-subtle)]">
          {category || strategyKey}
        </span>
        <span
          className={`mt-3 inline-flex items-center gap-1.5 text-[11px] font-medium ${
            selected ? "text-[var(--accent)]" : "text-[var(--fg-subtle)]"
          }`}
        >
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              selected ? "bg-[var(--accent)]" : "bg-[var(--fg-subtle)]"
            }`}
            aria-hidden
          />
          {selected ? "Selected" : "Available"}
        </span>
      </button>
    </li>
  );
}

export function strategyCardFromRecord(
  c: Record<string, unknown>,
  selectedKey: string,
  onSelectKey: (key: string, defaultParams: Record<string, unknown>) => void,
) {
  const key = str(c.key);
  return (
    <StrategyCard
      key={key}
      strategyKey={key}
      name={str(c.name)}
      category={str(c.category) || key}
      selected={selectedKey === key}
      onSelect={() => onSelectKey(key, asRecord(c.default_params))}
    />
  );
}
