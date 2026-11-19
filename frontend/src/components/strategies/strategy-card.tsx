"use client";

import { createElement } from "react";
import type { LucideIcon } from "lucide-react";
import { strategyIconForKey } from "@/components/strategies/strategy-icons";
import { Button } from "@/components/ui/button";
import { str } from "@/lib/desk";
import { cn } from "@/lib/utils";

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
  const title = name || strategyKey;
  return (
    <li className="h-full">
      <article
        className={cn(
          "qf-overview-card qf-overview-enter flex h-[18rem] flex-col gap-4 p-5",
          selected && "ring-2 ring-[var(--accent)]",
          !available && "opacity-70",
        )}
      >
        <div className="flex items-start justify-between gap-3">
          <span className="qf-overview-icon qf-overview-icon-sm" aria-hidden>
            {createElement(iconType, { className: "h-4 w-4" })}
          </span>
          <span className="rounded-full border border-[color-mix(in_srgb,var(--accent)_35%,var(--border))] bg-[var(--accent-soft)] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--accent)]">
            {(category || strategyKey).replaceAll("_", " ")}
          </span>
        </div>
        <h3 className="line-clamp-2 min-h-[2.75rem] text-base font-semibold tracking-tight text-[var(--fg)]">{title}</h3>
        <p className="line-clamp-3 min-h-[4.05rem] flex-1 text-sm leading-relaxed text-[var(--fg-muted)]">
          {description || "No description was returned for this strategy."}
        </p>
        <Button
          type="button"
          variant={selected ? "default" : "secondary"}
          className="mt-auto min-h-11 w-full"
          disabled={!available}
          aria-pressed={selected}
          onClick={onSelect}
        >
          View details
        </Button>
      </article>
    </li>
  );
}

export function strategyCardFromRecord(
  c: Record<string, unknown>,
  selectedKey: string,
  onSelectKey: (key: string) => void,
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
        onSelectKey(key);
      }}
    />
  );
}
