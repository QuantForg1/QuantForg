/**
 * Minimal, safe markdown → block model for assistant replies.
 * No HTML is ever injected: the renderer builds React nodes from these blocks.
 */
export type Inline = { text: string; bold: boolean };
export type Block =
  | { kind: "heading"; level: 1 | 2 | 3; inline: Inline[] }
  | { kind: "bullets"; items: Inline[][] }
  | { kind: "numbered"; items: Inline[][] }
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
    const b = /^[-*•]\s+(.*)$/.exec(t);
    if (b) {
      flush();
      const prev = blocks[blocks.length - 1];
      if (prev && prev.kind === "bullets") prev.items.push(parseInline(b[1]));
      else blocks.push({ kind: "bullets", items: [parseInline(b[1])] });
      continue;
    }
    const n = /^\d+[.)]\s+(.*)$/.exec(t);
    if (n) {
      flush();
      const prev = blocks[blocks.length - 1];
      if (prev && prev.kind === "numbered") prev.items.push(parseInline(n[1]));
      else blocks.push({ kind: "numbered", items: [parseInline(n[1])] });
      continue;
    }
    para.push(t);
  }
  flush();
  return blocks;
}
