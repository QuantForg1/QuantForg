/** Operator notes/tags for journal entries — client persistence only (no Trading Core). */

export type OperatorNote = {
  notes: string;
  tags: string[];
  updatedAt: string;
};

const KEY = "qf.operator.journal.notes.v1";

function loadAll(): Record<string, OperatorNote> {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Record<string, OperatorNote>) : {};
  } catch {
    return {};
  }
}

function saveAll(map: Record<string, OperatorNote>) {
  try {
    localStorage.setItem(KEY, JSON.stringify(map));
  } catch {
    /* ignore */
  }
}

export function getOperatorNote(tradeId: string): OperatorNote {
  return loadAll()[tradeId] ?? { notes: "", tags: [], updatedAt: "" };
}

export function setOperatorNote(
  tradeId: string,
  patch: Partial<Pick<OperatorNote, "notes" | "tags">>,
): OperatorNote {
  const all = loadAll();
  const prev = all[tradeId] ?? { notes: "", tags: [], updatedAt: "" };
  const next: OperatorNote = {
    notes: patch.notes ?? prev.notes,
    tags: patch.tags ?? prev.tags,
    updatedAt: new Date().toISOString(),
  };
  all[tradeId] = next;
  saveAll(all);
  return next;
}
