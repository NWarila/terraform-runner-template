# Release Gates

PRs to `main` on this template must pass:

- `actionlint` (workflow syntax)
- `workflow helper tests` (ShellCheck, workflow input binding checks, caller workflow checks, and contract tests)
- `markdownlint` (docs)
- `terraform runner verify` (`python tools/verify.py verify`, including runner contract, policy, docs, manifest, and integration)
- `org-baseline / verify` (drift-gate against `NWarila/.github` at pinned source-ref)
- `Trivy (filesystem & secrets)`, `Gitleaks (secret scan)`, `zizmor (Actions security)` (security)
- `CodeQL` (`security.yaml`)

OpenSSF Scorecard runs on push, branch-protection, schedule, and manual paths;
it is skipped on PR and merge queue because private-repo Scorecard GraphQL
access is not reliable.

All gates run via the workflows in `.github/workflows/`. The drift-gate workflow is SHA-pinned to [`NWarila/drift-gate`](https://github.com/NWarila/drift-gate); required consumer validation and security flow through `pr-validation.yaml`, `terraform-deploy.yaml`, and `security.yaml`. Release automation lives behind optional `release.yaml`.

Before tagging a runner-template release that changes deploy or backend wiring,
`Terraform Deploy` must also succeed on `main` or via manual dispatch in its S3
backend mode. This is intentionally post-merge because it assumes the AWS OIDC
role, applies the saved plan, and writes the template's real S3 state object.

Release evidence, when enabled, uploads the evidence bundle and SPDX SBOM as
release assets and emits GitHub artifact attestations for bundle provenance and
SBOM binding. Trusted-bot auto-merge is isolated in `auto-merge.yaml`.
