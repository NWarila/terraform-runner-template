# Release Gates

PRs to `main` on this template must pass:

- `actionlint` (workflow syntax)
- `shellcheck` (shell scripts)
- `yamllint` (workflows + manifests)
- `ruff` (Python tools)
- `markdownlint` (docs)
- `zizmor` (workflow security)
- `audit-tools-smoke-test` (tooling sanity + template contract self-validation + template scaffold manifest schema)
- `org-baseline / verify` (drift-gate against `nwarila-platform/.github` at pinned source-ref)
- `Trivy (filesystem & secrets)`, `Gitleaks (secret scan)`, `zizmor (Actions security)` (security)
- `CodeQL` (`security.yaml`)
- `OpenSSF Scorecard` (`security.yaml`)

All gates run via the workflows in `.github/workflows/`. The drift-gate workflow is SHA-pinned to [`NWarila/drift-gate`](https://github.com/NWarila/drift-gate); required consumer validation and security flow through `pr-validation.yaml`, `terraform-deploy.yaml`, and `security.yaml`. Release automation lives behind optional `release.yaml`.

Before tagging a runner-template release that changes deploy or backend wiring,
`Terraform Deploy` must also succeed on `main` or via manual dispatch in its S3
backend mode. This is intentionally post-merge because it assumes the AWS OIDC
role, applies the saved plan, and writes the template's real S3 state object.

Release evidence, when enabled, uploads the evidence bundle and SPDX SBOM as
release assets and emits GitHub artifact attestations for bundle provenance and
SBOM binding. Trusted-bot auto-merge is isolated in `auto-merge.yaml`.
