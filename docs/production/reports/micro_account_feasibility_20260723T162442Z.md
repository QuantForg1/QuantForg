# Micro Account Mode — Feasibility Report

- Generated at: `2026-07-23T16:24:42.572130+00:00`
- Mode: `MICRO_ACCOUNT_MODE`
- Symbol: `XAUUSD`
- Institutional Mode modified: **False**
- Institutional unchanged: Q=80 · C=80 · risk=1.0% · `ite-v1.0.0`

## Assumptions

- ATR=12.00 · multiplier=1.5 · stop=18.0000
- Broker min_lot=0.01 · contract_size=100 · dollar risk at min_lot=**$18.00**
- Formula: `dollar_risk = lots × stop_distance × contract_size`
- Recommended max risk: 2.0% · Hard max: 5.0%

## Feasibility by supported balance

| Equity | Min usable risk % | Smallest executable lot | Max loss / trade | Losses → 20% DD | Tradability |
|---:|---:|---:|---:|---:|---|
| $50 | 36.00% | — (reject) | $18.00 | 0 | **not_tradable** |
| $100 | 18.00% | — (reject) | $18.00 | 1 | **not_tradable** |
| $250 | 7.20% | — (reject) | $18.00 | 2 | **not_tradable** |
| $500 | 3.60% | 0.01 | $18.00 | 5 | **conditional** |

### $50 explicit finding

$50 cannot safely trade XAUUSD with broker min_lot 0.01 under mathematically correct sizing (would require 36.00% risk at ATR=12.00, stop=18.0000; hard max is 5.0%). Do not force execution.

## Exact balances where XAUUSD becomes safely tradable

- Exact equity floor for ≤2.0% (safe): **$900.00**
- Exact equity floor for ≤5.0% (hard max / conditional): **$360.00**
- Exact equity floor for Institutional 1%: **$1800.00**
- Safe among supported ladder ($50/$100/$250/$500): **none**
- Conditional among supported ladder: **['500']**

## Recommended micro-account policy

- Activation: `explicit_operator_selection_only` (enabled_by_default=False)
- Recommended max risk: 2.0% · Hard max: 5.0%
- If calculated lots < min_lot: **REJECT (approved_lots=0)**
- Never fake lots / bypass broker min / exceed hard max: **True** / **True** / **True**

- Do not enable MICRO_ACCOUNT_MODE for balances below $360.00 at ATR=12.00 (min_lot stop-loss exceeds hard max 5.0%).
- Treat balances ≥ $900.00 as the first ‘safe’ XAUUSD micro tier at ≤2.0% risk (still below Institutional 1% floor).
- Institutional 1% sizing with min_lot 0.01 requires equity ≥ $1800.00 at this stop — keep Institutional Mode for those accounts.
- If stuck at $50–$100: fund higher, or use a broker with 0.001 min lot — do not force 0.01 fills.

## ATR sensitivity

| ATR | Stop | $ risk @ 0.01 | Safe equity floor | Hard equity floor |
|---:|---:|---:|---:|---:|
| 8 | 12.0000 | $12.00 | $600.00 | $240.00 |
| 10 | 15.0000 | $15.00 | $750.00 | $300.00 |
| 12 | 18.0000 | $18.00 | $900.00 | $360.00 |
| 15 | 22.5000 | $22.50 | $1125.00 | $450.00 |
| 20 | 30.0000 | $30.00 | $1500.00 | $600.00 |

## Per-balance detail

### $50

- Broker min_lot 0.01 implies $18.00 loss (36.00% of $50), which exceeds hard_max_risk_pct=5.0%. Cannot execute without faking lots or exceeding max account risk.
- $50 cannot safely trade XAUUSD with broker min_lot 0.01 under mathematically correct sizing.
- Recommend: Higher account balance — ≥ $900.00 for ≤2.0% risk at current stop, or ≥ $360.00 for hard ceiling 5.0%.
- Recommend: Broker supporting smaller minimum lot (e.g. 0.001) — would cut dollar risk ~10× at the same stop.
- Recommend: Lower-risk instrument — not supported on QuantForg (XAUUSD-only platform).

### $100

- Broker min_lot 0.01 implies $18.00 loss (18.00% of $100), which exceeds hard_max_risk_pct=5.0%. Cannot execute without faking lots or exceeding max account risk.
- Recommend: Higher account balance — ≥ $900.00 for ≤2.0% risk at current stop, or ≥ $360.00 for hard ceiling 5.0%.
- Recommend: Broker supporting smaller minimum lot (e.g. 0.001) — would cut dollar risk ~10× at the same stop.
- Recommend: Lower-risk instrument — not supported on QuantForg (XAUUSD-only platform).

### $250

- Broker min_lot 0.01 implies $18.00 loss (7.20% of $250), which exceeds hard_max_risk_pct=5.0%. Cannot execute without faking lots or exceeding max account risk.
- Recommend: Higher account balance — ≥ $900.00 for ≤2.0% risk at current stop, or ≥ $360.00 for hard ceiling 5.0%.
- Recommend: Broker supporting smaller minimum lot (e.g. 0.001) — would cut dollar risk ~10× at the same stop.
- Recommend: Lower-risk instrument — not supported on QuantForg (XAUUSD-only platform).

### $500

- Executable at min_lot 0.01 only by accepting 3.60% risk (above recommended 2.0%, within hard max 5.0%).
- Recommend: Prefer higher equity so min_lot risk ≤ 2.0% (need ≥ $900.00).
- Recommend: Do not force Institutional 1% sizing — it would calculate sub-min lots and correctly reject (no upsize).
