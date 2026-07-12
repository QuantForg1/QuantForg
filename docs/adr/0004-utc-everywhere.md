# ADR-0004: UTC Everywhere

## Status

Accepted

## Context

Trading platforms span venues, sessions, and daylight-saving transitions.
Storing or comparing naive local timestamps causes off-by-one-hour bugs,
incorrect session resolution, and irreproducible analysis.

## Decision

**All instants inside QuantForg are timezone-aware UTC.**

Rules:

1. Persist and exchange timestamps as UTC (`datetime` with `tzinfo=UTC`).
2. Reject or normalise naive datetimes at domain boundaries (`ensure_utc`).
3. Convert to IANA local zones only at the edge (display, session windows,
   calendars) using `zoneinfo`.
4. Domain events carry `occurred_at` in UTC.
5. Logs and APIs expose ISO-8601 UTC (trailing `Z` or explicit offset).

Session and calendar logic may use local wall times for *windows*, but the
instant being classified is always UTC.

## Consequences

**Positive**

- Deterministic comparisons and ordering across engines.
- DST handled at conversion boundaries, not in core arithmetic.
- Simpler multi-region operations.

**Negative**

- Callers must attach timezone info; naive `datetime.now()` is forbidden.
- Human readers sometimes prefer local time in UIs (conversion required).

**Neutral**

- Date-only calendar facts remain local civil dates where the calendar
  definition requires it, derived from a UTC instant + IANA zone.

## Alternatives Considered

| Alternative | Why rejected |
|---|---|
| Store broker-local times as source of truth | Ambiguous across venues and DST |
| Naive datetimes “assumed UTC” | Silent corruption; fails under DST |
| Epoch millis only | Poor ergonomics; still need UTC policy for conversion |

## References

- [docs/market-context.md](../market-context.md)
- Python `zoneinfo` / `datetime.UTC`
- ADR-0007 Analysis Pipeline
- ADR-0008 MarketAnalysisSnapshot
