# Security Policy

## Reporting vulnerabilities

**Do not** open public GitHub issues for security vulnerabilities.

Email **security@quantforg.com** (or the private security contact listed in
the GitHub repository Security tab) with:

- Description and impact
- Reproduction steps / proof of concept
- Affected versions / commit SHA
- Your preferred credit name (optional)

We aim to acknowledge within **72 hours** and provide a remediation plan for
confirmed issues.

## Supported versions

| Version | Supported |
|---|---|
| Latest `main` / latest released `0.y.z` | Yes |
| Older 0.x releases | Best effort only |

## Engineering requirements

1. **Secrets**: never commit API keys, broker passwords, JWT secrets, or
   private certificates. Use `.env` (gitignored) and secret managers in
   production.
2. **Dependencies**: keep Dependabot alerts triageable; do not ignore high
   severity without mitigation notes.
3. **Least privilege**: DB/cache roles and API tokens scoped narrowly.
4. **Input validation**: validate at boundaries (Pydantic / domain VOs).
5. **Logging**: never log secrets, session tokens, or full payment data.
6. **Analysis vs execution**: analysis cannot move capital (ADR-0010);
   AI cannot execute (ADR-0015); MT5 stays adapter-side (ADR-0014).
7. **Plugins**: treat third-party plugins as untrusted; run behind ports and
   risk gates (ADR-0006, ADR-0013).

## Incident response (summary)

1. Contain (rotate secrets, disable unsafe flags/adapters).
2. Assess blast radius and affected users.
3. Patch, release, and communicate.
4. Post-incident notes for internal learning (no sensitive customer data).

## Secure development checklist

- [ ] No credentials in git history for this change
- [ ] AuthN/AuthZ reviewed if endpoints changed
- [ ] Dangerous operations are audited
- [ ] Third-party adapters fail closed on auth errors
