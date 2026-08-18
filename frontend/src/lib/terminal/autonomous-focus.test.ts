/**
 * Terminal view vs autonomous execution symbol.
 * Run: node --experimental-strip-types src/lib/terminal/autonomous-focus.test.ts
 */
import assert from "node:assert/strict";
import {
  bookIntegrityFromCycle,
  extractAuthorizedExecution,
  focusObservability,
  initialTerminalFocus,
  MANUAL_HOME_SYMBOL,
  nextTerminalFocus,
  symbolsEquivalent,
  symbolsFromBookRows,
  type TerminalFocusState,
} from "./autonomous-focus";

function apply(
  prev: TerminalFocusState,
  partial: Parameters<typeof nextTerminalFocus>[1],
): TerminalFocusState {
  return nextTerminalFocus(prev, {
    homeSymbol: MANUAL_HOME_SYMBOL,
    manualSymbol: MANUAL_HOME_SYMBOL,
    authorized: null,
    openPositionSymbols: [],
    pendingOrderSymbols: [],
    bookIntegrity: "ok",
    userSelected: false,
    ...partial,
  });
}

const home = initialTerminalFocus("XAUUSD_i");
assert.equal(home.mode, "MANUAL");
assert.equal(home.terminalSymbol, "XAUUSD_i");
assert.equal(home.symbolSource, "MANUAL");
assert.equal(MANUAL_HOME_SYMBOL, "XAUUSD_i");

// 1 + 2. Terminal=XAUUSD_i does not block autonomous NZDUSD_I (UI state only)
{
  const focused = apply(home, {
    authorized: { symbol: "NZDUSD_I", authKey: "t1" },
  });
  assert.equal(focused.mode, "AUTONOMOUS_EXECUTING");
  assert.equal(focused.terminalSymbol, "NZDUSD_i");
  assert.equal(focused.manualSymbol, "XAUUSD_i");
  assert.equal(focused.symbolSource, "AUTONOMOUS_EXECUTION");
  assert.equal(focused.autonomousSymbol, "NZDUSD_i");
}

// Scanner BEST_ELIGIBLE without OMS authorization does not steal focus
{
  const scanOnly = extractAuthorizedExecution({
    orchestrator: {
      last_cycle: {
        forwarded_to_oms: false,
        decision_action: "WATCH",
        market_context_diagnostics: { symbol: "NZDUSD_I" },
      },
    },
  });
  assert.equal(scanOnly, null);
  const stayed = apply(home, { authorized: scanOnly });
  assert.equal(stayed.mode, "MANUAL");
  assert.equal(stayed.terminalSymbol, "XAUUSD_i");
}

// 6. Focus follows candidate only after execution authorization
{
  const authorized = extractAuthorizedExecution({
    orchestrator: {
      last_cycle: {
        forwarded_to_oms: true,
        decision_action: "BUY",
        trace_id: "cycle-nzd",
        abort_reason: "NONE",
        market_context_diagnostics: { symbol: "NZDUSD_I" },
      },
    },
  });
  assert.equal(authorized?.symbol, "NZDUSD_i");
  const focused = apply(home, { authorized });
  assert.equal(focused.mode, "AUTONOMOUS_EXECUTING");
  assert.equal(focused.terminalSymbol, "NZDUSD_i");
}

// 7. Autonomous position opens → stay on traded symbol
{
  const opened = apply(
    apply(home, { authorized: { symbol: "NZDUSD_I", authKey: "t1" } }),
    { openPositionSymbols: ["NZDUSD_I"] },
  );
  assert.equal(opened.mode, "AUTONOMOUS_POSITION_OPEN");
  assert.equal(opened.terminalSymbol, "NZDUSD_i");
  assert.equal(opened.sawAutonomousPosition, true);
}

// 8. Autonomous position closes → return to XAUUSD_i
{
  const closed = apply(
    apply(home, {
      authorized: { symbol: "NZDUSD_I", authKey: "t1" },
      openPositionSymbols: ["NZDUSD_I"],
    }),
    {
      authorized: { symbol: "NZDUSD_I", authKey: "t1" },
      openPositionSymbols: [],
      bookIntegrity: "ok",
    },
  );
  assert.equal(closed.mode, "MANUAL");
  assert.equal(closed.terminalSymbol, "XAUUSD_i");
  assert.equal(closed.symbolSource, "MANUAL");
}

// Stale last_cycle after close must not re-enter focus
{
  const afterClose = apply(
    apply(
      apply(home, {
        authorized: { symbol: "NZDUSD_I", authKey: "t1" },
        openPositionSymbols: ["NZDUSD_I"],
      }),
      {
        authorized: { symbol: "NZDUSD_I", authKey: "t1" },
        openPositionSymbols: [],
      },
    ),
    { authorized: { symbol: "NZDUSD_I", authKey: "t1" } },
  );
  assert.equal(afterClose.mode, "MANUAL");
  assert.equal(afterClose.terminalSymbol, "XAUUSD_i");
}

// 9. Multiple autonomous positions → remain AUTONOMOUS_FOCUS
{
  const multi = apply(home, {
    openPositionSymbols: ["NZDUSD_I", "EURUSD_I"],
  });
  assert.equal(multi.mode, "AUTONOMOUS_POSITION_OPEN");
  const still = apply(multi, {
    openPositionSymbols: ["EURUSD_I"],
  });
  assert.equal(still.mode, "AUTONOMOUS_POSITION_OPEN");
  assert.ok(["NZDUSD_i", "EURUSD_i"].includes(still.terminalSymbol));
}

// 10. UNKNOWN / RECONCILIATION_REQUIRED → do not return to manual
{
  const focused = apply(home, {
    openPositionSymbols: ["NZDUSD_I"],
  });
  const unknown = apply(focused, {
    openPositionSymbols: [],
    bookIntegrity: "unknown",
  });
  assert.equal(unknown.mode, "AUTONOMOUS_RECONCILIATION");
  assert.equal(unknown.terminalSymbol, "NZDUSD_i");

  const recon = apply(focused, {
    openPositionSymbols: [],
    bookIntegrity: "reconciliation_required",
  });
  assert.equal(recon.mode, "AUTONOMOUS_RECONCILIATION");
}

{
  const integrity = bookIntegrityFromCycle(
    {
      orchestrator: {
        last_cycle: {
          cycle_outcome: "RECONCILIATION_REQUIRED",
          abort_reason: "UNKNOWN",
        },
      },
    },
    { healthKnown: true, gatewayOnline: true },
  );
  assert.equal(integrity, "reconciliation_required");
}

// 11. No autonomous candidate → remain on manual symbol
{
  const stayed = apply(home, { authorized: null, openPositionSymbols: [] });
  assert.equal(stayed.mode, "MANUAL");
  assert.equal(stayed.terminalSymbol, "XAUUSD_i");
}

// 12. Manual user selection works in MANUAL mode
{
  const picked = apply(home, {
    manualSymbol: "EURUSD_i",
    userSelected: true,
  });
  assert.equal(picked.mode, "MANUAL");
  assert.equal(picked.terminalSymbol, "EURUSD_i");
  assert.equal(picked.symbolSource, "MANUAL");
}

// Manual pick does not override an open autonomous position
{
  const live = apply(home, { openPositionSymbols: ["NZDUSD_I"] });
  const ignored = apply(live, {
    manualSymbol: "XAUUSD_i",
    userSelected: true,
    openPositionSymbols: ["NZDUSD_I"],
  });
  assert.equal(ignored.mode, "AUTONOMOUS_POSITION_OPEN");
  assert.equal(ignored.terminalSymbol, "NZDUSD_i");
}

// Manual pick consumes stale authorization so last_cycle cannot steal focus
{
  const picked = apply(home, {
    manualSymbol: "XAUUSD_i",
    userSelected: true,
    authorized: { symbol: "NZDUSD_I", authKey: "stale" },
  });
  const stayed = apply(picked, {
    authorized: { symbol: "NZDUSD_I", authKey: "stale" },
  });
  assert.equal(stayed.mode, "MANUAL");
  assert.equal(stayed.terminalSymbol, "XAUUSD_i");
}

assert.equal(symbolsEquivalent("NZDUSD_I", "NZDUSD_i"), true);
assert.deepEqual(symbolsFromBookRows([{ symbol: "NZDUSD_I" }]), ["NZDUSD_I"]);

{
  const obs = focusObservability(
    apply(home, { authorized: { symbol: "NZDUSD_I", authKey: "t1" } }),
  );
  assert.equal(obs.terminal_symbol, "NZDUSD_i");
  assert.equal(obs.manual_symbol, "XAUUSD_i");
  assert.equal(obs.execution_symbol, "NZDUSD_i");
  assert.equal(obs.symbol_source, "AUTONOMOUS_EXECUTION");
  assert.equal(obs.terminal_mode, "AUTONOMOUS_EXECUTING");
}

{
  const fromCanonical = apply(home, {
    canonical: {
      terminal_mode: "AUTONOMOUS_EXECUTING",
      execution_symbol: "NZDUSD_I",
      broker_symbol: "NZDUSD_I",
      symbol: "NZDUSD_I",
      manual_symbol: "XAUUSD_i",
      symbol_source: "AUTONOMOUS_EXECUTION",
      execution_status: "EXECUTING",
      mt5_status: "MT5_CONNECTED",
      mt5_chart_symbol: null,
      mt5_chart_sync: "unsupported",
      position_symbols: [],
      open_position_count: 0,
      unresolved_order_count: 1,
      failure_mode: "NONE",
      order_id: "4242",
      position_id: null,
    },
  });
  assert.equal(fromCanonical.mode, "AUTONOMOUS_EXECUTING");
  assert.equal(fromCanonical.terminalSymbol, "NZDUSD_i");
  assert.equal(fromCanonical.manualSymbol, "XAUUSD_i");
}

console.log("autonomous-focus.test.ts: ok");
