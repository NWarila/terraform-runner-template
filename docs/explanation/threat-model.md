# Threat Model

## Scope

What this template guarantees:

- Every consumer runner enforces the universal quality-gate set on every
  PR (codeql, scorecard, IaC security, ADR drift detection).
- Workflow `uses:` references are SHA-pinned; tag/branch references are
  rejected by the contract validator and OPA policy.
- Terraform and provider versions are exact-pinned in consumed
  frameworks; the `pr-validation` runner mode invokes the framework's
  pinned versions, not the runner's preference.
- Org-baseline ADRs cannot drift undetected; the [`drift-gate`
  workflow](../../.github/workflows/drift-gate.yaml) (calling
  [`NWarila/drift-gate`](https://github.com/NWarila/drift-gate))
  runs on every PR with byte-equality assertions and inline
  annotations on drifted files.

## Out of scope

What this template does NOT guarantee:

- Branch protection on consumer runner repos. Required status checks
  are configured per-repo in GitHub Settings, not from this template.
  Without branch protection, a maintainer can merge a red PR.
- The consumed framework's correctness. If the framework is broken,
  runner deploys break — but the runner's `pr-validation` would catch
  it before merge by running `make ci` against the assembled tree.
- AWS credentials handling. Runners use OIDC via
  `aws-actions/configure-aws-credentials` with `mask-aws-account-id:
  true`; the role permissions are configured outside this template.

Cross-reference: `SECURITY.md` (in `<owner>/.github`) defines the
org-level reporting channel and the org-wide scope boundary.
