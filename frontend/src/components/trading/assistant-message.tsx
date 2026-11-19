"use client";

import { Fragment } from "react";
import { parseMarkdown, type Inline } from "@/lib/assistant/markdown";

function InlineText({ parts }: { parts: Inline[] }) {
  return (
    <>
      {parts.map((p, i) =>
        p.bold ? (
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

/** Renders an assistant reply from a safe block model (no raw HTML). */
export function AssistantMarkdown({ text }: { text: string }) {
  const blocks = parseMarkdown(text);
  return (
    <div className="space-y-2.5 text-sm leading-relaxed">
      {blocks.map((b, i) => {
        switch (b.kind) {
          case "heading":
            return (
              <p
                key={i}
                className={
                  b.level === 1
                    ? "pt-1 text-base font-semibold"
                    : "pt-1 text-sm font-semibold text-[var(--accent)]"
                }
              >
                <InlineText parts={b.inline} />
              </p>
            );
          case "bullets":
            return (
              <ul key={i} className="list-disc space-y-1 pl-5 marker:text-[var(--accent)]">
                {b.items.map((it, j) => (
                  <li key={j}>
                    <InlineText parts={it} />
                  </li>
                ))}
              </ul>
            );
          case "numbered":
            return (
              <ol key={i} className="list-decimal space-y-1 pl-5 marker:text-[var(--accent)]">
                {b.items.map((it, j) => (
                  <li key={j}>
                    <InlineText parts={it} />
                  </li>
                ))}
              </ol>
            );
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
