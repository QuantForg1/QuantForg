/**
 * Minimal, safe markdown → block model for assistant replies.
 * No HTML is ever injected: the renderer builds React nodes from these blocks.
 */
export type Inline = { text: string; bold: boolean };
export type ListItem = { inline: Inline[]; children: Inline[][] };
export type Block =
  | { kind: "heading"; level: 1 | 2 | 3; inline: Inline[] }
  | { kind: "bullets"; items: ListItem[] }
  | { kind: "numbered"; items: ListItem[] }
  | { kind: "paragraph"; inline: Inline[] }
  | { kind: "rule" };

export function parseInline(text: string): Inline[] {
  const out: Inline[] = [];
  const re = /\*\*([^*]+)\*\*|__([^_]+)__/g;
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push({ text: text.slice(last, m.index), bold: false });
    out.push({ text: m[1] ?? m[2] ?? "", bold: true });
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push({ text: text.slice(last), bold: false });
  return out.filter((p) => p.text.length > 0);
}

export function parseMarkdown(src: string): Block[] {
  const blocks: Block[] = [];
  let para: string[] = [];
  const flush = () => {
    if (para.length) {
      blocks.push({ kind: "paragraph", inline: parseInline(para.join(" ")) });
      para = [];
    }
  };
  for (const raw of src.replace(/\r\n/g, "\n").split("\n")) {
    const line = raw.trimEnd();
    const t = line.trim();
    if (t === "") {
      flush();
      continue;
    }
    if (/^(-{3,}|\*{3,}|_{3,})$/.test(t)) {
      flush();
      blocks.push({ kind: "rule" });
      continue;
    }
    const h = /^(#{1,6})\s+(.*)$/.exec(t);
    if (h) {
      flush();
      const level = Math.min(3, h[1].length) as 1 | 2 | 3;
      blocks.push({ kind: "heading", level, inline: parseInline(h[2].replace(/#+$/, "").trim()) });
      continue;
    }
    const indent = line.replace(/\t/g, "  ").search(/\S/);
    const b = /^[-*•]\s+(.*)$/.exec(t);
    const n = b ? null : /^\d+[.)]\s+(.*)$/.exec(t);
    if (b || n) {
      flush();
      const content = parseInline((b ?? n)![1]);
      const kind = b ? "bullets" : "numbered";
      const prev = blocks[blocks.length - 1];
      const prevList = prev && (prev.kind === "bullets" || prev.kind === "numbered") ? prev : null;
      if (prevList && indent >= 2 && prevList.items.length > 0) {
        prevList.items[prevList.items.length - 1].children.push(content);
      } else if (prevList && prevList.kind === kind) {
        prevList.items.push({ inline: content, children: [] });
      } else {
        blocks.push({ kind, items: [{ inline: content, children: [] }] });
      }
      continue;
    }
    para.push(t);
  }
  flush();
  return blocks;
}
