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

export type TerminalMode = "MANUAL" | "AUTONOMOUS_FOCUS";
export type SymbolSource = "MANUAL" | "AUTONOMOUS_EXECUTION";
export type BookIntegrity = "ok" | "unknown" | "reconciliation_required";

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
};

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
  symbol_source: SymbolSource;
  terminal_mode: TerminalMode;
} {
  return {
    terminal_symbol: state.terminalSymbol,
    manual_symbol: state.manualSymbol,
    autonomous_symbol: state.autonomousSymbol,
    execution_symbol: state.autonomousSymbol,
    symbol_source: state.symbolSource,
    terminal_mode: state.mode,
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
  ]);
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
      mode: "AUTONOMOUS_FOCUS",
      terminalSymbol: stay,
      manualSymbol: manual,
      autonomousSymbol: stay,
      symbolSource: "AUTONOMOUS_EXECUTION",
      sawAutonomousPosition: true,
      consumedAuthKey: prev.consumedAuthKey,
    };
  }

  if (unresolvedBook(input.bookIntegrity) && prev.mode === "AUTONOMOUS_FOCUS") {
    return { ...prev, manualSymbol: manual };
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

  if (authorized && !(prev.mode === "AUTONOMOUS_FOCUS" && prev.sawAutonomousPosition)) {
    return {
      mode: "AUTONOMOUS_FOCUS",
      terminalSymbol: authorized.symbol,
      manualSymbol: manual,
      autonomousSymbol: authorized.symbol,
      symbolSource: "AUTONOMOUS_EXECUTION",
      sawAutonomousPosition: prev.sawAutonomousPosition,
      consumedAuthKey: prev.consumedAuthKey,
    };
  }

  if (prev.mode === "AUTONOMOUS_FOCUS") {
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
