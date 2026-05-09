# Release Gates

PRs to `main` on this template must pass:

- `actionlint` (workflow syntax)
- `shellcheck` (shell scripts)
- `yamllint` (workflows + manifests)
- `ruff` (Python tools)
- `markdownlint` (docs)
- `zizmor` (workflow security)
- `audit-tools-smoke-test` (tooling sanity + contract / baseline-manifest schemas)
- `org-baseline / verify` (drift-gate against `nwarila-platform/.github` at pinned source-ref)
- `Trivy (filesystem & secrets)`, `Gitleaks (secret scan)`, `zizmor (Actions security)` (security)
- `analyze` (CodeQL)
- `analysis` (Scorecard)

All gates run via the workflows in `.github/workflows/`. The drift-gate workflow is SHA-pinned to [`NWarila/drift-gate`](https://github.com/NWarila/drift-gate); the other reusables (`reusable-codeql.yaml`, `reusable-scorecard.yaml`, `reusable-iac-security.yaml`, `reusable-auto-merge.yaml`, `reusable-release-please.yaml`, `reusable-release-evidence.yaml`, `reusable-terraform-validation.yaml`) live in this repo and are referenced by consumer runners via SHA-pinned `uses:` lines.
