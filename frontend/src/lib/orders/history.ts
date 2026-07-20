/** Pair live MT5 deals into closed trades and derive analytics — no mocks. */

export type LiveDeal = {
  ticket: number;
  order_ticket: number;
  symbol: string;
  side: "buy" | "sell" | string;
  volume: number;
  price: number;
  profit: number;
  commission: number;
  swap: number;
  deal_type: string;
  time: Date;
  magic: number;
  comment: string;
  position_id: number;
};

export type LiveTrade = {
  id: string;
  time: Date;
  symbol: string;
  side: "buy" | "sell";
  volume: number;
  entry: number;
  exit: number | null;
  sl: number | null;
  tp: number | null;
  commission: number;
  swap: number;
  profit: number;
  netPl: number;
  durationMs: number | null;
  ticket: number;
  deal: number;
  entryDeal: number;
  exitDeal: number | null;
  strategy: string;
  comment: string;
  status: "closed" | "open";
  timeline: { label: string; at: Date; detail: string }[];
};

function n(v: unknown, fallback = 0): number {
  const x = Number(v);
  return Number.isFinite(x) ? x : fallback;
}

export function parseLiveDeal(row: Record<string, unknown>): LiveDeal | null {
  const ticket = n(row.ticket);
  const symbol = String(row.symbol || "")
    .trim()
    .toUpperCase();
  if (ticket <= 0 || !symbol) return null;
  const rawTime = row.time;
  let time = new Date();
  if (typeof rawTime === "string" || typeof rawTime === "number") {
    const d = new Date(rawTime);
    if (!Number.isNaN(d.getTime())) time = d;
  }
  return {
    ticket,
    order_ticket: n(row.order_ticket, ticket),
    symbol,
    side: String(row.side || "buy").toLowerCase(),
    volume: n(row.volume),
    price: n(row.price),
    profit: n(row.profit),
    commission: n(row.commission),
    swap: n(row.swap),
    deal_type: String(row.deal_type || "").toLowerCase(),
    time,
    magic: n(row.magic),
    comment: String(row.comment || ""),
    position_id: n(row.position_id),
  };
}

function isEntry(d: LiveDeal): boolean {
  return d.deal_type.includes("in") || d.deal_type === "entry_in";
}

function isExit(d: LiveDeal): boolean {
  return d.deal_type.includes("out") || d.deal_type === "entry_out";
}

/** Pair entry/exit deals from live gateway history into trades. */
export function pairDealsIntoTrades(deals: LiveDeal[]): LiveTrade[] {
  const sorted = [...deals].sort((a, b) => a.time.getTime() - b.time.getTime());
  const byPos = new Map<number, LiveDeal[]>();
  const unpaired: LiveDeal[] = [];

  for (const d of sorted) {
    if (d.position_id > 0) {
      const list = byPos.get(d.position_id) ?? [];
      list.push(d);
      byPos.set(d.position_id, list);
    } else {
      unpaired.push(d);
    }
  }

  const trades: LiveTrade[] = [];

  for (const [posId, group] of byPos) {
    const entries = group.filter(isEntry);
    const exits = group.filter(isExit);
    const entry = entries[0] ?? group[0];
    const exit = exits[exits.length - 1] ?? null;
    if (!entry) continue;
    trades.push(buildTrade(entry, exit, posId));
  }

  // FIFO fallback when position_id is missing
  const openBySymbol = new Map<string, LiveDeal[]>();
  for (const d of unpaired) {
    if (isEntry(d) || (!isExit(d) && d.profit === 0)) {
      const q = openBySymbol.get(d.symbol) ?? [];
      q.push(d);
      openBySymbol.set(d.symbol, q);
      continue;
    }
    if (isExit(d)) {
      const q = openBySymbol.get(d.symbol) ?? [];
      const entry = q.shift();
      openBySymbol.set(d.symbol, q);
      if (entry) trades.push(buildTrade(entry, d, entry.order_ticket || entry.ticket));
      else trades.push(buildTrade(d, d, d.ticket));
    }
  }
  for (const q of openBySymbol.values()) {
    for (const entry of q) {
      trades.push(buildTrade(entry, null, entry.order_ticket || entry.ticket));
    }
  }

  return trades.sort((a, b) => b.time.getTime() - a.time.getTime());
}

function buildTrade(entry: LiveDeal, exit: LiveDeal | null, ticket: number): LiveTrade {
  const commission = entry.commission + (exit?.commission ?? 0);
  const swap = entry.swap + (exit?.swap ?? 0);
  const profit = entry.profit + (exit?.profit ?? 0);
  const netPl = profit + swap + commission;
  const side: "buy" | "sell" = entry.side === "sell" ? "sell" : "buy";
  const strategy =
    entry.magic > 0
      ? `magic:${entry.magic}`
      : exit && exit.magic > 0
        ? `magic:${exit.magic}`
        : "";
  const comment = [entry.comment, exit?.comment].filter(Boolean).join(" · ");
  const timeline = [
    {
      label: "Entry deal",
      at: entry.time,
      detail: `${entry.side.toUpperCase()} ${entry.volume} @ ${entry.price} · deal ${entry.ticket}`,
    },
  ];
  if (exit) {
    timeline.push({
      label: "Exit deal",
      at: exit.time,
      detail: `${exit.side.toUpperCase()} ${exit.volume} @ ${exit.price} · deal ${exit.ticket} · P/L ${exit.profit}`,
    });
  }
  return {
    id: `${ticket}-${entry.ticket}-${exit?.ticket ?? "open"}`,
    time: exit?.time ?? entry.time,
    symbol: entry.symbol,
    side,
    volume: entry.volume,
    entry: entry.price,
    exit: exit?.price ?? null,
    sl: null,
    tp: null,
    commission,
    swap,
    profit,
    netPl,
    durationMs: exit ? Math.max(0, exit.time.getTime() - entry.time.getTime()) : null,
    ticket,
    deal: exit?.ticket ?? entry.ticket,
    entryDeal: entry.ticket,
    exitDeal: exit?.ticket ?? null,
    strategy,
    comment,
    status: exit ? "closed" : "open",
    timeline,
  };
}

export type HistoryRange = "today" | "week" | "month" | "custom";

export function rangeToIso(range: HistoryRange, customFrom?: string, customTo?: string): {
  date_from: string;
  date_to: string;
} {
  const now = new Date();
  const to = new Date(now);
  to.setHours(23, 59, 59, 999);
  let from = new Date(now);
  if (range === "today") {
    from.setHours(0, 0, 0, 0);
  } else if (range === "week") {
    from.setDate(from.getDate() - 7);
    from.setHours(0, 0, 0, 0);
  } else if (range === "month") {
    from.setDate(1);
    from.setHours(0, 0, 0, 0);
  } else {
    from = customFrom ? new Date(customFrom) : from;
    const end = customTo ? new Date(customTo) : to;
    return { date_from: from.toISOString(), date_to: end.toISOString() };
  }
  return { date_from: from.toISOString(), date_to: to.toISOString() };
}

export type TradeAnalytics = {
  winRate: number | null;
  profitFactor: number | null;
  averageRr: number | null;
  maxDrawdown: number | null;
  equityCurve: { t: number; equity: number }[];
  balanceCurve: { t: number; balance: number }[];
  dailyPl: { day: string; pl: number }[];
  monthlyReturns: { month: string; pl: number }[];
  closedCount: number;
  sharpe: number | null;
  sortino: number | null;
  recoveryFactor: number | null;
  largestWin: number | null;
  largestLoss: number | null;
  avgHoldMs: number | null;
  bySymbol: { label: string; value: number }[];
  bySession: { label: string; value: number }[];
  byHour: { label: string; value: number }[];
  byWeekday: { label: string; value: number }[];
  holdBuckets: { label: string; value: number }[];
  profitDistribution: { label: string; value: number }[];
  todayPl: number;
  weekPl: number;
  monthPl: number;
};

function sessionOf(d: Date): string {
  const h = d.getUTCHours();
  if (h >= 7 && h < 12) return "London";
  if (h >= 12 && h < 17) return "Overlap";
  if (h >= 12 && h < 21) return "New York";
  if (h >= 0 && h < 7) return "Asia";
  return "Off";
}

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

export function computeTradeAnalytics(
  trades: LiveTrade[],
  { startingEquity = 0 }: { startingEquity?: number } = {},
): TradeAnalytics {
  const closed = trades.filter((t) => t.status === "closed");
  const wins = closed.filter((t) => t.netPl > 0);
  const losses = closed.filter((t) => t.netPl < 0);
  const grossWin = wins.reduce((s, t) => s + t.netPl, 0);
  const grossLoss = Math.abs(losses.reduce((s, t) => s + t.netPl, 0));
  const winRate = closed.length ? wins.length / closed.length : null;
  const profitFactor =
    grossLoss > 0 ? grossWin / grossLoss : wins.length ? null : null;
  const avgWin = wins.length ? grossWin / wins.length : 0;
  const avgLoss = losses.length ? grossLoss / losses.length : 0;
  const averageRr = avgLoss > 0 ? avgWin / avgLoss : null;

  const chronological = [...closed].sort(
    (a, b) => a.time.getTime() - b.time.getTime(),
  );
  let equity = startingEquity;
  let peak = startingEquity;
  let maxDd = 0;
  const equityCurve: { t: number; equity: number }[] = [];
  const balanceCurve: { t: number; balance: number }[] = [];
  const dailyMap = new Map<string, number>();
  const monthlyMap = new Map<string, number>();
  const returns: number[] = [];
  const downside: number[] = [];
  let prevEquity = startingEquity;

  for (const t of chronological) {
    equity += t.netPl;
    const ret = prevEquity !== 0 ? t.netPl / Math.abs(prevEquity) : 0;
    returns.push(ret);
    if (ret < 0) downside.push(ret);
    prevEquity = equity;
    peak = Math.max(peak, equity);
    maxDd = Math.max(maxDd, peak - equity);
    equityCurve.push({ t: t.time.getTime(), equity });
    balanceCurve.push({ t: t.time.getTime(), balance: equity });
    const day = t.time.toISOString().slice(0, 10);
    dailyMap.set(day, (dailyMap.get(day) ?? 0) + t.netPl);
    const month = t.time.toISOString().slice(0, 7);
    monthlyMap.set(month, (monthlyMap.get(month) ?? 0) + t.netPl);
  }

  const mean =
    returns.length > 0 ? returns.reduce((a, b) => a + b, 0) / returns.length : 0;
  const variance =
    returns.length > 1
      ? returns.reduce((s, r) => s + (r - mean) ** 2, 0) / (returns.length - 1)
      : 0;
  const std = Math.sqrt(variance);
  const sharpe = std > 0 ? mean / std : null;
  const downMean =
    downside.length > 0 ? downside.reduce((a, b) => a + b, 0) / downside.length : 0;
  const downVar =
    downside.length > 1
      ? downside.reduce((s, r) => s + (r - downMean) ** 2, 0) / (downside.length - 1)
      : 0;
  const downStd = Math.sqrt(downVar);
  const sortino = downStd > 0 ? mean / downStd : null;
  const netProfit = chronological.reduce((s, t) => s + t.netPl, 0);
  const recoveryFactor = maxDd > 0 ? netProfit / maxDd : null;

  const largestWin = wins.length ? Math.max(...wins.map((t) => t.netPl)) : null;
  const largestLoss = losses.length ? Math.min(...losses.map((t) => t.netPl)) : null;
  const holds = closed
    .map((t) => t.durationMs)
    .filter((ms): ms is number => ms != null && Number.isFinite(ms));
  const avgHoldMs = holds.length
    ? holds.reduce((a, b) => a + b, 0) / holds.length
    : null;

  const bySymbolMap = new Map<string, number>();
  const bySessionMap = new Map<string, number>();
  const byHourMap = new Map<string, number>();
  const byWeekdayMap = new Map<string, number>();
  for (const t of closed) {
    bySymbolMap.set(t.symbol, (bySymbolMap.get(t.symbol) ?? 0) + t.netPl);
    const sess = sessionOf(t.time);
    bySessionMap.set(sess, (bySessionMap.get(sess) ?? 0) + t.netPl);
    const hour = `${String(t.time.getUTCHours()).padStart(2, "0")}:00`;
    byHourMap.set(hour, (byHourMap.get(hour) ?? 0) + t.netPl);
    const wd = WEEKDAYS[t.time.getUTCDay()] ?? "—";
    byWeekdayMap.set(wd, (byWeekdayMap.get(wd) ?? 0) + t.netPl);
  }

  const holdBuckets = [
    { label: "<15m", value: 0 },
    { label: "15m–1h", value: 0 },
    { label: "1–4h", value: 0 },
    { label: "4h+", value: 0 },
  ];
  for (const ms of holds) {
    const m = ms / 60000;
    if (m < 15) holdBuckets[0]!.value += 1;
    else if (m < 60) holdBuckets[1]!.value += 1;
    else if (m < 240) holdBuckets[2]!.value += 1;
    else holdBuckets[3]!.value += 1;
  }

  const profitDistribution = [
    { label: "Wins", value: wins.length },
    { label: "Losses", value: losses.length },
    { label: "Flat", value: closed.filter((t) => t.netPl === 0).length },
  ];

  const now = new Date();
  const startToday = new Date(now);
  startToday.setHours(0, 0, 0, 0);
  const startWeek = new Date(now);
  startWeek.setDate(startWeek.getDate() - 7);
  const startMonth = new Date(now.getFullYear(), now.getMonth(), 1);
  const todayPl = closed
    .filter((t) => t.time >= startToday)
    .reduce((s, t) => s + t.netPl, 0);
  const weekPl = closed
    .filter((t) => t.time >= startWeek)
    .reduce((s, t) => s + t.netPl, 0);
  const monthPl = closed
    .filter((t) => t.time >= startMonth)
    .reduce((s, t) => s + t.netPl, 0);

  const toRows = (m: Map<string, number>) =>
    [...m.entries()]
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([label, value]) => ({ label, value }));

  return {
    winRate,
    profitFactor,
    averageRr,
    maxDrawdown: chronological.length ? maxDd : null,
    equityCurve,
    balanceCurve,
    dailyPl: toRows(dailyMap).map((r) => ({ day: r.label, pl: r.value })),
    monthlyReturns: toRows(monthlyMap).map((r) => ({ month: r.label, pl: r.value })),
    closedCount: closed.length,
    sharpe,
    sortino,
    recoveryFactor,
    largestWin,
    largestLoss,
    avgHoldMs,
    bySymbol: toRows(bySymbolMap),
    bySession: toRows(bySessionMap),
    byHour: toRows(byHourMap),
    byWeekday: WEEKDAYS.map((d) => ({
      label: d,
      value: byWeekdayMap.get(d) ?? 0,
    })),
    holdBuckets,
    profitDistribution,
    todayPl,
    weekPl,
    monthPl,
  };
}

export function inferTradeSession(time: Date): string {
  return sessionOf(time);
}

export function computeTradeRr(t: LiveTrade): number | null {
  if (t.sl == null || t.sl <= 0) return null;
  const risk = Math.abs(t.entry - t.sl);
  if (risk <= 0) return null;
  if (t.exit == null) return null;
  const reward = Math.abs(t.exit - t.entry);
  return reward / risk;
}

export function attachStopsFromPositions(
  trades: LiveTrade[],
  positions: { ticket: number; stop_loss?: number; take_profit?: number }[],
): LiveTrade[] {
  if (!positions.length) return trades;
  const byTicket = new Map(positions.map((p) => [p.ticket, p]));
  return trades.map((t) => {
    const pos = byTicket.get(t.ticket);
    if (!pos) return t;
    const sl = pos.stop_loss != null && pos.stop_loss > 0 ? pos.stop_loss : t.sl;
    const tp = pos.take_profit != null && pos.take_profit > 0 ? pos.take_profit : t.tp;
    return { ...t, sl, tp };
  });
}

export function formatDuration(ms: number | null): string {
  if (ms == null || !Number.isFinite(ms)) return "—";
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ${s % 60}s`;
  const h = Math.floor(m / 60);
  if (h < 48) return `${h}h ${m % 60}m`;
  const d = Math.floor(h / 24);
  return `${d}d ${h % 24}h`;
}

export function tradesToCsv(trades: LiveTrade[]): string {
  const headers = [
    "Time",
    "Symbol",
    "Side",
    "Volume",
    "Entry",
    "Exit",
    "SL",
    "TP",
    "Commission",
    "Swap",
    "Profit",
    "NetPL",
    "DurationMs",
    "Ticket",
    "Deal",
    "Strategy",
    "Comment",
    "Status",
  ];
  const lines = [headers.join(",")];
  for (const t of trades) {
    lines.push(
      [
        t.time.toISOString(),
        t.symbol,
        t.side,
        t.volume,
        t.entry,
        t.exit ?? "",
        t.sl ?? "",
        t.tp ?? "",
        t.commission,
        t.swap,
        t.profit,
        t.netPl,
        t.durationMs ?? "",
        t.ticket,
        t.deal,
        JSON.stringify(t.strategy),
        JSON.stringify(t.comment),
        t.status,
      ].join(","),
    );
  }
  return lines.join("\n");
}
