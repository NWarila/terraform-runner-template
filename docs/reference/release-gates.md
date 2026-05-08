# Release Gates

PRs to `main` on this template must pass:

- `actionlint` (workflow syntax)
- `shellcheck` (shell scripts)
- `yamllint` (workflows + manifests)
- `ruff` (Python tools)
- `markdownlint` (docs)
- `zizmor` (workflow security)
- `audit-tools-smoke-test` (tooling sanity + contract/sync manifests)
- `Verify org ADR mirrors` (org-adr-sync)
- `Trivy (filesystem & secrets)`, `Gitleaks (secret scan)`, `zizmor (Actions security)` (security)
- `analyze` (CodeQL)
- `analysis` (Scorecard)

All gates run via the workflows in `.github/workflows/`; the universal
reusables (codeql, scorecard, security, auto-merge, org-adr-sync,
release-please, release-evidence, template-sync) are synced from
`terraform-template-template` via canonical-baseline-sync and must be
SHA-pinned per the contract.
