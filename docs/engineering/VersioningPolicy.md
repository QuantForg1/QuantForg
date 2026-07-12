# Versioning Policy

QuantForg uses **Semantic Versioning 2.0.0**: `MAJOR.MINOR.PATCH`.

## While on 0.y.z

- `0.y.z` means the public API is **not stable**.
- Breaking changes may occur in minor bumps; still document them clearly in
  CHANGELOG as **BREAKING**.
- Prefer additive changes when possible.

## After 1.0.0

| Bump | When |
|---|---|
| MAJOR | Breaking API, event, or plugin-contract changes |
| MINOR | Backward-compatible features |
| PATCH | Backward-compatible bug fixes |

## What counts as a public contract

- Documented HTTP APIs
- Domain/integration event types and payloads
- Plugin ports and metadata schemas
- Published Python package interfaces marked public

Internal modules without documentation guarantees may change without MAJOR
bumps, but prefer not to surprise in-repo consumers.

## Event & plugin contracts

- Follow ADR-0009 for events.
- Plugin ABI breaks require MAJOR (or a new plugin contract version field).

## Artifacts

- Git tags: `vMAJOR.MINOR.PATCH`
- `pyproject.toml` `version` must match the tag
- Container tags mirror SemVer

## Pre-releases

Optional suffixes: `1.2.0-rc.1`, `1.2.0-beta.1`. Pre-releases are not
production defaults.
