# Contributing to QuantForg

Thank you for contributing. This repository is an **AI-powered algorithmic
trading platform** under active foundation development. Many capabilities
(live trading, MT5, AI advisors, strategies) are **architecturally reserved**
and must follow ADRs even when not yet implemented.

## Before you start

1. Read [docs/architecture-governance.md](docs/architecture-governance.md).
2. Skim binding ADRs in [docs/adr/](docs/adr/README.md) — especially
   ADR-0001, ADR-0010, ADR-0014, and ADR-0015.
3. Follow [docs/engineering/CodingStandards.md](docs/engineering/CodingStandards.md).

## Development setup

```bash
./scripts/bootstrap.sh
make check
```

See [docs/development.md](docs/development.md) for day-to-day commands.

## Workflow

1. Create a branch per [BranchStrategy.md](docs/engineering/BranchStrategy.md).
2. Commit with [CommitConvention.md](docs/engineering/CommitConvention.md).
3. Ensure [DefinitionOfDone.md](docs/engineering/DefinitionOfDone.md) is met.
4. Open a PR using the pull request template.
5. Address [CodeReviewChecklist.md](docs/engineering/CodeReviewChecklist.md)
   feedback. Architecture-impacting PRs also need the
   [ArchitectureReviewChecklist.md](docs/engineering/ArchitectureReviewChecklist.md).

## What we accept now

- Domain analysis engines behind ports (no execution)
- Application use cases, DTOs, tests
- Infrastructure adapters that do **not** bypass risk/architecture rules
- Documentation, ADRs, CI, and developer experience improvements

## What we reject without an ADR exception

- Trade execution from analysis code
- MT5 types or calls inside `domain/`
- Autonomous AI order placement
- Strategies that bypass the future risk engine
- `float` money/price paths; naive datetimes as source of truth

## Security

Report vulnerabilities privately per
[SecurityPolicy.md](docs/engineering/SecurityPolicy.md).
Do not file public issues for exploitable security bugs.

## License

Proprietary — see [LICENSE](LICENSE). Contributors must have permission to
submit changes under the project license.
