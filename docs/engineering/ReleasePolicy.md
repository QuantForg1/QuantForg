# Release Policy

## Versioning

QuantForg follows [VersioningPolicy.md](VersioningPolicy.md) (SemVer).

Current foundation series starts at **0.y.z** (public API not stable).

## Release train

1. Ensure `main` is green.
2. Update `CHANGELOG.md`: move `[Unreleased]` notes into `## [x.y.z] - YYYY-MM-DD`.
3. Bump version in `pyproject.toml` (and any lock metadata via Poetry).
4. Tag annotated release: `git tag -a vX.Y.Z -m "QuantForg vX.Y.Z"`.
5. Push `main` and tags; publish GitHub Release notes from CHANGELOG.
6. Deploy per [docs/deployment.md](../deployment.md).

## Pre-release checklist

- [ ] CI green on the release commit.
- [ ] Migrations reviewed; rollback notes captured if applicable.
- [ ] No temporary feature flags left in an unsafe default.
- [ ] Security review for auth, secrets, and dependency alerts.
- [ ] Architecture constraints intact (no accidental MT5/AI execution in core).

## Hotfix releases

- Branch from the tagged release if needed, or fix forward on `main` if safe.
- Bump patch version; document in CHANGELOG under **Fixed**.

## Artifacts

- Container images tagged `vX.Y.Z` and optionally `latest` for non-prod.
- Never promote an untagged local build to production.

## Yanking

If a release is critically broken, publish a higher patch and mark the GitHub
Release as broken; do not rewrite tags already consumed by production.
