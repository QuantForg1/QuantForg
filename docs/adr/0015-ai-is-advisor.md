# ADR-0015: AI Is Advisor

## Status

Accepted

## Context

QuantForg is branded as AI-powered, but autonomous model output must not
silently move capital. Models hallucinate, drift, and lack fiduciary
accountability. The platform needs a hard stance on AI’s authority.

## Decision

**AI is an advisor, never an autonomous trader.**

Rules:

1. AI components are plugins/adapters (ADR-0006) that produce **advice**,
   explanations, rankings, or critiques.
2. AI must not place orders, bypass risk, or mutate positions directly.
3. AI inputs are snapshots, features derived from approved analysis, and
   explicit prompts — not raw broker sockets.
4. AI outputs are non-authoritative: strategies/humans/risk decide.
5. Domain analysis engines (structure, liquidity, context) are **not** AI;
   they are deterministic domain services.
6. Prompts, model versions, and advice payloads are auditable when used for
   decisions.
7. Current sprints exclude AI implementation; this ADR constrains future work.

## Consequences

**Positive**

- Clear safety story for users and reviewers.
- Deterministic analysis remains trustworthy and testable.
- AI can still add value without owning execution.

**Negative**

- “Fully autonomous AI trading” is explicitly out of product architecture.
- Extra UX/application glue to present advice vs action.

**Neutral**

- Offline research notebooks may use models freely; production paths obey
  this ADR.

## Alternatives Considered

| Alternative | Why rejected |
|---|---|
| AI agent calls execution API | Unacceptable capital and compliance risk |
| Replace structure/liquidity engines with LLMs | Non-deterministic, untestable “analysis” |
| AI inside risk with auto-approve | Conflicts with fail-closed independent risk |

## References

- ADR-0006 Plugin Architecture
- ADR-0010 Analysis Never Trades
- ADR-0012 Strategy Is Plugin
- ADR-0013 Risk Engine Independent
- [Architecture Governance Guide](../architecture-governance.md)
