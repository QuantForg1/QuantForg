# Commit Convention

QuantForg follows **Conventional Commits**.

## Format

```
<type>(<optional scope>): <short summary>

[optional body]

[optional footer]
```

### Types

| Type | Use for |
|---|---|
| `feat` | New user-visible capability |
| `fix` | Bug fix |
| `docs` | Documentation / ADR / governance only |
| `test` | Tests only |
| `refactor` | Internal restructuring without behaviour change |
| `perf` | Performance improvement |
| `chore` | Tooling, deps, CI |
| `build` | Packaging / Docker |
| `ci` | CI workflows |
| `revert` | Reverts a prior commit |

### Scopes (suggested)

`domain`, `application`, `infrastructure`, `presentation`, `core`,
`market-context`, `market-structure`, `liquidity`, `events`, `docs`, `adr`,
`ci`

### Examples

```
feat(liquidity): add equal-high sweep detection

docs(adr): accept ADR-0010 analysis never trades

fix(market-structure): stabilize swing uuid5 identities

test(liquidity): cover multi-symbol snapshot isolation
```

## Rules

1. Imperative mood: “add”, not “added”.
2. Summary ≤ 72 characters when practical.
3. Body explains **why**, not a restatement of the diff.
4. Reference issues: `Closes #123` in footer when applicable.
5. **Never** commit secrets. If a secret was committed, rotate immediately
   and follow [SecurityPolicy.md](SecurityPolicy.md).
6. Prefer small commits that tell a story; squash optional at merge.

## Relation to CHANGELOG

`feat` / `fix` / breaking changes should appear under `[Unreleased]` in
CHANGELOG.md before release.
