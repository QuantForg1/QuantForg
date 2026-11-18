"use client";

import { createElement } from "react";
import type { LucideIcon } from "lucide-react";
import { strategyIconForKey } from "@/components/strategies/strategy-icons";
import { asRecord, str } from "@/lib/desk";

type StrategyCardProps = {
  strategyKey: string;
  name: string;
  category: string;
  description?: string;
  available?: boolean;
  selected: boolean;
  onSelect: () => void;
  icon?: LucideIcon;
};

export function StrategyCard({
  strategyKey,
  name,
  category,
  description = "",
  available = true,
  selected,
  onSelect,
  icon,
}: StrategyCardProps) {
  const iconType = icon ?? strategyIconForKey(strategyKey);
  return (
    <li className="h-full">
      <button
        type="button"
        disabled={!available}
        className={`flex h-full min-h-[10.5rem] w-full flex-col rounded-[var(--radius-os)] border px-3 py-3 text-left transition duration-[var(--duration-fast)] ${
          selected
            ? "border-[var(--accent)] bg-[var(--accent-soft)] shadow-[0_0_0_1px_color-mix(in_srgb,var(--accent)_42%,transparent)]"
            : "border-[var(--border)] bg-[var(--surface)] hover:border-[var(--border-strong)]"
        } disabled:cursor-not-allowed disabled:opacity-70`}
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
        <span className="line-clamp-2 min-h-[2.5rem] text-sm font-semibold text-[var(--fg)]">{name}</span>
        <span className="mt-1 text-[11px] font-medium uppercase tracking-[0.08em] text-[var(--fg-subtle)]">
          {category || strategyKey}
        </span>
        <span className="mt-1 line-clamp-2 min-h-[2rem] text-xs text-[var(--fg-muted)]">
          {description}
        </span>
        <span
          className={`mt-auto inline-flex items-center gap-1.5 pt-3 text-[11px] font-medium ${
            selected ? "text-[var(--accent)]" : "text-[var(--fg-subtle)]"
          }`}
        >
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              selected ? "bg-[var(--accent)]" : "bg-[var(--fg-subtle)]"
            }`}
            aria-hidden
          />
          {selected ? "Selected" : available ? "Available" : "Not selectable"}
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
  const available = c.enabled !== false && c.available !== false && c.selectable !== false;
  return (
    <StrategyCard
      key={key}
      strategyKey={key}
      name={str(c.name)}
      category={str(c.category) || key}
      description={str(c.description)}
      available={available}
      selected={selectedKey === key}
      onSelect={() => {
        if (!available) return;
        onSelectKey(key, asRecord(c.default_params));
      }}
    />
  );
}
