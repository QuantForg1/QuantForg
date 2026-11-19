"use client";

import { Fragment } from "react";
import { parseMarkdown, type Inline, type ListItem } from "@/lib/assistant/markdown";

function InlineText({ parts }: { parts: Inline[] }) {
  return (
    <>
      {parts.map((p, i) =>
        p.href ? (
          <a
            key={i}
            href={p.href}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[var(--accent)] underline underline-offset-2 hover:brightness-125"
          >
            {p.text}
          </a>
        ) : p.bold ? (
          <strong key={i} className="font-semibold text-[var(--fg)]">
            {p.text}
          </strong>
        ) : (
          <Fragment key={i}>{p.text}</Fragment>
        ),
      )}
    </>
  );
}

function List({ ordered, items }: { ordered: boolean; items: ListItem[] }) {
  const Tag = ordered ? "ol" : "ul";
  return (
    <Tag
      className={
        (ordered ? "list-decimal" : "list-disc") +
        " space-y-1.5 pl-5 marker:text-[var(--accent)]"
      }
    >
      {items.map((it, j) => (
        <li key={j} className="pl-0.5">
          <InlineText parts={it.inline} />
          {it.children.length > 0 ? (
            <ul className="mt-1 list-[circle] space-y-1 pl-5 text-[var(--fg-muted)] marker:text-[var(--fg-subtle)]">
              {it.children.map((c, k) => (
                <li key={k}>
                  <InlineText parts={c} />
                </li>
              ))}
            </ul>
          ) : null}
        </li>
      ))}
    </Tag>
  );
}

/** Renders an assistant reply from a safe block model (no raw HTML). */
export function AssistantMarkdown({ text, compact = false }: { text: string; compact?: boolean }) {
  const blocks = parseMarkdown(text);
  return (
    <div
      className={
        compact
          ? "space-y-1.5 text-xs leading-relaxed"
          : "space-y-2.5 text-[0.9rem] leading-relaxed text-[var(--fg)]"
      }
    >
      {blocks.map((b, i) => {
        switch (b.kind) {
          case "heading":
            return (
              <p
                key={i}
                className={
                  b.level === 1
                    ? "pt-1 text-base font-semibold"
                    : "pt-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--accent)]"
                }
              >
                <InlineText parts={b.inline} />
              </p>
            );
          case "bullets":
          case "numbered":
            return <List key={i} ordered={b.kind === "numbered"} items={b.items} />;
          case "rule":
            return <hr key={i} className="border-[var(--border)]" />;
          default:
            return (
              <p key={i}>
                <InlineText parts={b.inline} />
              </p>
            );
        }
      })}
    </div>
  );
}
