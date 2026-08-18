/**
 * Terminal chart focus vs autonomous execution authority.
 *
 * Terminal selected symbol is VIEW / UI context only.
 * Autonomous orders are built from executionDecision.symbol on the backend.
 * This module never submits orders and never overrides OMS / Safety / Risk.
 */

import { asRecord } from "@/lib/desk";
import { resolveTradingSymbol, TRADING_SYMBOL } from "@/lib/trading/gold-only";

export const MANUAL_HOME_SYMBOL = TRADING_SYMBOL;

export type TerminalMode =
  | "MANUAL"
  | "AUTONOMOUS_PENDING"
  | "AUTONOMOUS_EXECUTING"
  | "AUTONOMOUS_POSITION_OPEN"
  | "AUTONOMOUS_POSITION_CLOSING"
  | "AUTONOMOUS_RECONCILIATION"
  | "RETURNING_TO_MANUAL"
  | "AUTONOMOUS_FOCUS";

export type SymbolSource = "MANUAL" | "AUTONOMOUS_EXECUTION";
export type BookIntegrity = "ok" | "unknown" | "reconciliation_required";

export function isAutonomousTerminalMode(mode: TerminalMode): boolean {
  return mode !== "MANUAL" && mode !== "RETURNING_TO_MANUAL";
}

export type AuthorizedExecution = {
  symbol: string;
  authKey: string;
};

export type TerminalFocusState = {
  mode: TerminalMode;
  terminalSymbol: string;
  manualSymbol: string;
  autonomousSymbol: string | null;
  symbolSource: SymbolSource;
  sawAutonomousPosition: boolean;
  consumedAuthKey: string | null;
};

export type TerminalFocusInput = {
  homeSymbol?: string;
  manualSymbol: string;
  authorized: AuthorizedExecution | null;
  openPositionSymbols: string[];
  pendingOrderSymbols: string[];
  bookIntegrity: BookIntegrity;
  userSelected: boolean;
  canonical?: CanonicalExecutionContext | null;
};

export type CanonicalExecutionContext = {
  terminal_mode: string;
  execution_symbol: string | null;
  broker_symbol: string | null;
  symbol: string | null;
  manual_symbol: string;
  symbol_source: string;
  execution_status: string;
  mt5_status: string;
  mt5_chart_symbol: string | null;
  mt5_chart_sync: string;
  position_symbols: string[];
  open_position_count: number;
  unresolved_order_count: number;
  failure_mode: string;
  order_id: string | null;
  position_id: string | null;
};

export function extractCanonicalContext(
  payload: unknown,
): CanonicalExecutionContext | null {
  const ctx = asRecord(asRecord(payload).execution_context);
  if (!Object.keys(ctx).length) return null;
  const positions = Array.isArray(ctx.position_symbols)
    ? ctx.position_symbols.map((item) => String(item))
    : [];
  return {
    terminal_mode: String(ctx.terminal_mode || "MANUAL"),
    execution_symbol: ctx.execution_symbol
      ? String(ctx.execution_symbol)
      : ctx.symbol
        ? String(ctx.symbol)
        : null,
    broker_symbol: ctx.broker_symbol ? String(ctx.broker_symbol) : null,
    symbol: ctx.symbol ? String(ctx.symbol) : null,
    manual_symbol: String(ctx.manual_symbol || MANUAL_HOME_SYMBOL),
    symbol_source: String(ctx.symbol_source || "MANUAL"),
    execution_status: String(ctx.execution_status || ctx.status || "IDLE"),
    mt5_status: String(ctx.mt5_status || ""),
    mt5_chart_symbol: ctx.mt5_chart_symbol ? String(ctx.mt5_chart_symbol) : null,
    mt5_chart_sync: String(ctx.mt5_chart_sync || "unsupported"),
    position_symbols: positions,
    open_position_count: Number(ctx.open_position_count || 0),
    unresolved_order_count: Number(ctx.unresolved_order_count || 0),
    failure_mode: String(ctx.failure_mode || "NONE"),
    order_id: ctx.order_id != null ? String(ctx.order_id) : null,
    position_id: ctx.position_id != null ? String(ctx.position_id) : null,
  };
}

export function initialTerminalFocus(manualSymbol?: string): TerminalFocusState {
  const home = resolveTradingSymbol(manualSymbol || MANUAL_HOME_SYMBOL);
  return {
    mode: "MANUAL",
    terminalSymbol: home,
    manualSymbol: home,
    autonomousSymbol: null,
    symbolSource: "MANUAL",
    sawAutonomousPosition: false,
    consumedAuthKey: null,
  };
}

export function symbolsEquivalent(a: string, b: string): boolean {
  return (
    resolveTradingSymbol(a).toUpperCase() ===
    resolveTradingSymbol(b).toUpperCase()
  );
}

function uniqResolved(symbols: string[]): string[] {
  const out: string[] = [];
  for (const raw of symbols) {
    const code = String(raw || "").trim();
    if (!code || code === "—") continue;
    const resolved = resolveTradingSymbol(code);
    if (!out.some((item) => symbolsEquivalent(item, resolved))) {
      out.push(resolved);
    }
  }
  return out;
}

function unresolvedBook(integrity: BookIntegrity): boolean {
  return integrity === "unknown" || integrity === "reconciliation_required";
}

export function symbolsFromBookRows(
  rows: ReadonlyArray<Record<string, unknown>>,
): string[] {
  return rows
    .map((row) => {
      const value = row.symbol ?? row.code;
      return typeof value === "string" ? value.trim() : "";
    })
    .filter(Boolean);
}

export function extractAuthorizedExecution(
  payload: unknown,
): AuthorizedExecution | null {
  const root = asRecord(payload);
  const orch = asRecord(root.orchestrator ?? root);
  const last = asRecord(orch.last_cycle);
  const forwarded = Boolean(last.forwarded_to_oms);
  const ticket = last.mt5_ticket;
  const hasTicket = ticket != null && String(ticket).trim() !== "";
  if (!forwarded && !hasTicket) return null;

  const action = String(last.decision_action || "").toUpperCase();
  if (action && action !== "BUY" && action !== "SELL") return null;

  const abort = String(last.abort_reason || "").toUpperCase();
  const abortSoft = abort === "" || abort === "NONE" || abort === "OK" || abort === "SUCCESS";
  if (!abortSoft && !hasTicket) return null;

  const diag = asRecord(last.market_context_diagnostics);
  let raw = String(diag.symbol || "").trim();
  if (!raw) {
    const attempts = Array.isArray(root.recent_execution_attempts)
      ? root.recent_execution_attempts
      : [];
    raw = String(asRecord(attempts[0]).symbol || "").trim();
  }
  if (!raw) return null;

  const symbol = resolveTradingSymbol(raw);
  const authKey = String(
    last.trace_id || last.signal_id || `${symbol}:${hasTicket ? String(ticket) : "fwd"}`,
  );
  return { symbol, authKey };
}

export function bookIntegrityFromCycle(
  payload: unknown,
  session: {
    healthKnown: boolean;
    gatewayOnline: boolean | null;
  },
): BookIntegrity {
  const root = asRecord(payload);
  const orch = asRecord(root.orchestrator ?? root);
  const last = asRecord(orch.last_cycle);
  const outcome = String(last.cycle_outcome || "").toUpperCase();
  const abort = String(last.abort_reason || "").toUpperCase();
  if (
    outcome.includes("RECONCIL") ||
    abort.includes("RECONCIL") ||
    abort === "UNKNOWN"
  ) {
    return "reconciliation_required";
  }
  if (!session.healthKnown || session.gatewayOnline == null) return "unknown";
  if (session.gatewayOnline === false) return "unknown";
  return "ok";
}

export function focusObservability(state: TerminalFocusState): {
  terminal_symbol: string;
  manual_symbol: string;
  autonomous_symbol: string | null;
  execution_symbol: string | null;
  broker_symbol: string | null;
  mt5_chart_symbol: string | null;
  symbol_source: SymbolSource;
  terminal_mode: TerminalMode;
  execution_status: string;
  mt5_status: string;
} {
  return {
    terminal_symbol: state.terminalSymbol,
    manual_symbol: state.manualSymbol,
    autonomous_symbol: state.autonomousSymbol,
    execution_symbol: state.autonomousSymbol,
    broker_symbol: state.autonomousSymbol,
    mt5_chart_symbol: null,
    symbol_source: state.symbolSource,
    terminal_mode: state.mode,
    execution_status: state.mode,
    mt5_status: "",
  };
}

export function sameTerminalFocus(
  a: TerminalFocusState,
  b: TerminalFocusState,
): boolean {
  return (
    a.mode === b.mode &&
    a.terminalSymbol === b.terminalSymbol &&
    a.manualSymbol === b.manualSymbol &&
    a.autonomousSymbol === b.autonomousSymbol &&
    a.symbolSource === b.symbolSource &&
    a.sawAutonomousPosition === b.sawAutonomousPosition &&
    a.consumedAuthKey === b.consumedAuthKey
  );
}

export function nextTerminalFocus(
  prev: TerminalFocusState,
  input: TerminalFocusInput,
): TerminalFocusState {
  const home = resolveTradingSymbol(input.homeSymbol || MANUAL_HOME_SYMBOL);
  const manual = resolveTradingSymbol(input.manualSymbol || home);
  const live = uniqResolved([
    ...input.openPositionSymbols,
    ...input.pendingOrderSymbols,
    ...(input.canonical?.position_symbols ?? []),
  ]);
  const canonical = input.canonical;
  const canonicalMode = (canonical?.terminal_mode || "") as TerminalMode;
  const reconciling =
    unresolvedBook(input.bookIntegrity) ||
    canonicalMode === "AUTONOMOUS_RECONCILIATION" ||
    (canonical?.failure_mode || "").toUpperCase().includes("RECONCIL") ||
    (canonical?.execution_status || "").toUpperCase().includes("RECONCIL");
  const authorizedRaw =
    input.authorized && input.authorized.authKey !== prev.consumedAuthKey
      ? input.authorized
      : null;
  const authorized = authorizedRaw
    ? {
        symbol: resolveTradingSymbol(authorizedRaw.symbol),
        authKey: authorizedRaw.authKey,
      }
    : null;

  if (live.length > 0) {
    const stay =
      prev.autonomousSymbol &&
      live.some((item) => symbolsEquivalent(item, prev.autonomousSymbol!))
        ? resolveTradingSymbol(prev.autonomousSymbol)
        : live[0];
    return {
      mode: "AUTONOMOUS_POSITION_OPEN",
      terminalSymbol: stay,
      manualSymbol: manual,
      autonomousSymbol: stay,
      symbolSource: "AUTONOMOUS_EXECUTION",
      sawAutonomousPosition: true,
      consumedAuthKey: prev.consumedAuthKey,
    };
  }

  if (
    reconciling &&
    (isAutonomousTerminalMode(prev.mode) ||
      canonicalMode === "AUTONOMOUS_RECONCILIATION")
  ) {
    const stay = resolveTradingSymbol(
      prev.autonomousSymbol ||
        canonical?.broker_symbol ||
        canonical?.execution_symbol ||
        "",
    );
    if (stay) {
      return {
        mode: "AUTONOMOUS_RECONCILIATION",
        terminalSymbol: stay,
        manualSymbol: manual,
        autonomousSymbol: stay,
        symbolSource: "AUTONOMOUS_EXECUTION",
        sawAutonomousPosition: prev.sawAutonomousPosition,
        consumedAuthKey: prev.consumedAuthKey,
      };
    }
  }

  if (input.userSelected) {
    return {
      mode: "MANUAL",
      terminalSymbol: manual,
      manualSymbol: manual,
      autonomousSymbol: null,
      symbolSource: "MANUAL",
      sawAutonomousPosition: false,
      consumedAuthKey: input.authorized?.authKey ?? prev.consumedAuthKey,
    };
  }

  const execSymbol =
    authorized?.symbol ||
    (canonical?.broker_symbol
      ? resolveTradingSymbol(canonical.broker_symbol)
      : null) ||
    (canonical?.execution_symbol
      ? resolveTradingSymbol(canonical.execution_symbol)
      : null);

  const enterExecuting =
    Boolean(authorized) ||
    canonicalMode === "AUTONOMOUS_EXECUTING" ||
    canonical?.execution_status === "EXECUTING";

  if (
    enterExecuting &&
    execSymbol &&
    !(isAutonomousTerminalMode(prev.mode) && prev.sawAutonomousPosition)
  ) {
    return {
      mode: "AUTONOMOUS_EXECUTING",
      terminalSymbol: execSymbol,
      manualSymbol: manual,
      autonomousSymbol: execSymbol,
      symbolSource: "AUTONOMOUS_EXECUTION",
      sawAutonomousPosition: prev.sawAutonomousPosition,
      consumedAuthKey: prev.consumedAuthKey,
    };
  }

  if (isAutonomousTerminalMode(prev.mode)) {
    return {
      mode: "MANUAL",
      terminalSymbol: home,
      manualSymbol: home,
      autonomousSymbol: null,
      symbolSource: "MANUAL",
      sawAutonomousPosition: false,
      consumedAuthKey: authorized?.authKey ?? prev.consumedAuthKey,
    };
  }

  return {
    mode: "MANUAL",
    terminalSymbol: manual,
    manualSymbol: manual,
    autonomousSymbol: null,
    symbolSource: "MANUAL",
    sawAutonomousPosition: false,
    consumedAuthKey: prev.consumedAuthKey,
  };
}
