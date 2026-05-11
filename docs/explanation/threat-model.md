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
  it before merge by running the framework quality gate against the assembled tree.
- AWS credentials handling. Runners use OIDC via
  `aws-actions/configure-aws-credentials` with `mask-aws-account-id:
  true`; the role permissions are configured outside this template.

## Elevation of Privilege

The auto-merge workflow runs on `pull_request_target`, so its primary
elevation-of-privilege risk is a PR author causing a write-scoped token to
merge unreviewed code. The reusable keeps that boundary narrow:

- Authorization happens in a read-only job and reads only event metadata
  (`pull_request.user.login`, `pull_request.user.type`, and the PR number).
- The write-token job runs only after the author matches a closed bot list:
  `renovate[bot]` or `dependabot[bot]`.
- The GitHub Actions automation bot is deliberately not trusted. It is a shared
  automation identity, so trusting it would let unrelated workflows become
  auto-merge principals.
- The reusable has no caller-supplied extra author list. Adding a new
  auto-merge principal requires changing the reusable itself.
- OPA rejects checkout, PR-head refs, and other PR-controlled content reads in
  the auto-merge reusable and in `pull_request_target` callers.

Release automation uses the repository `GITHUB_TOKEN` and is not an auto-merge
principal. Release PRs opened by `github-actions[bot]` require human review.
This keeps fresh repos zero-setup while avoiding blanket trust in the shared
GitHub Actions automation identity. The release-please reusable requests only
the permissions it needs (`contents`, `pull-requests`, `issues`, and `actions`)
and uses `workflow_dispatch` to start release evidence for newly-created tags.

Cross-reference: `SECURITY.md` (in `<owner>/.github`) defines the
org-level reporting channel and the org-wide scope boundary.
