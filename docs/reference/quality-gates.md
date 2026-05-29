# Quality Gates

Each automated check enforced by this repository plays one of four roles. The
role determines *when* the check runs and *what failure means*.

| Role | Meaning | When it runs |
| --- | --- | --- |
| **Blocking** | Required for PR merge to `main`. Failure blocks the PR. | `pull_request` / `merge_group` triggers in `ci.yaml`, `drift-gate.yaml`, `security.yaml` |
| **Scheduled** | Periodic posture telemetry. Runs on a cron; does **not** block PRs. | `schedule` trigger in `security.yaml` |
| **Release** | Runs at release-cut time. Failure blocks the release tag and prevents the evidence bundle from being attached. | `release.yaml` and the reusables it calls |
| **Advisory** | Surfaces signal without blocking. Reserved for steps whose *publishing channel* is best-effort, or where the gate is explicitly opt-in. | Specific steps marked `continue-on-error: true` (see below) |

For the canonical list of required PR checks see
[release-gates.md](release-gates.md). This document classifies each gate's
role and explains the few places where `continue-on-error` is allowed.

## Gate inventory

| Gate | Source | Role | Notes |
| --- | --- | --- | --- |
| workflow-helper-tests | `ci.yaml` job `workflow-helper-tests` (runs `verify.py workflow-helper-tests`) | Blocking | ShellCheck, `check_workflow_run_blocks.py`, `check_caller_workflows.py`, `check_privileged_workflows.py` + fixture runner. |
| privileged-workflows | `verify.py workflow-helper-tests` (transitive) and `verify.py ci` (via `verify.py verify`) | Blocking | `check_privileged_workflows.py` + fixture-driven test runner. Rejects `actions/checkout` and PR-controlled refs in any `pull_request_target` workflow, transitively through local reusables. |
| runner verify (`verify.py verify`) | `ci.yaml` job that runs `verify.py verify` | Blocking | Wraps lint, OPA (test + repo-hygiene + plan), manifest, contract checks (`check_template_contract.py`, `run_contract_tests.py`), docs, ADR schema, integration. |
| consumer contract fixtures | `run_contract_tests.py` (via `contract-check`) | Blocking | `good/` and `bad-*/` consumer/contract fixtures under `tests/fixtures/`. Each `bad-*` must fail with documented `[FAIL]` markers. |
| drift-gate | `drift-gate.yaml` | Blocking | Dual-layer baseline drift check (org `NWarila/.github` + framework template). |
| Trivy IaC misconfig + secrets | `security.yaml` -> `reusable-iac-security.yaml` (PR path) | Blocking | Trivy scan exit status is the gate; SARIF upload is advisory (see below). |
| Gitleaks | `security.yaml` -> `reusable-iac-security.yaml` | Blocking by default | Caller-configurable via `inputs.gitleaks_advisory`. |
| zizmor (Actions posture) | `security.yaml` -> `reusable-iac-security.yaml` | Blocking | zizmor exit status is the gate; SARIF upload is advisory. |
| CodeQL | `security.yaml` -> `reusable-codeql.yaml` | Blocking | Static analysis. SARIF upload is advisory. |
| OpenSSF Scorecard | `security.yaml` -> `reusable-scorecard.yaml` | Scheduled / push / branch protection / manual; skipped on PR and merge queue | Posture telemetry; skipped on PR paths because Scorecard GraphQL is gated on private repos. |
| reusable validation lint jobs | `reusable-terraform-validation.yaml` jobs `actionlint`, `shellcheck`, `yamllint`, `ruff`, `markdownlint` | Blocking by default | Caller-configurable via `inputs.lint_advisory` for transition-only consumers. |
| pr-validation reference caller | `pr-validation.yaml` (`pull_request`, `workflow_dispatch`) | Blocking / manual | Runner-mode validation reference. Runs automatically on PRs and remains manually invokable to exercise the framework's reusable validation against this repo. |
| terraform-deploy (golden runner) | `terraform-deploy.yaml` | Manual / push to main | Reference runner deploy (AWS OIDC, S3 backend). Not run on PRs. |
| Release evidence + SBOM + attestations | `release.yaml` -> framework `reusable-release-evidence.yaml@<sha>` (`repo_type: runner`) | Release | Calls the Terraform framework template's reusable by SHA; runners own no local copy. Produces evidence bundle, SPDX SBOM, attestations. |
| Auto-merge (trusted bots) | `auto-merge.yaml` -> `reusable-auto-merge.yaml` | Not a gate | Operates on `pull_request_target` with no PR checkout; must keep passing `privileged-workflows`. |

## When `continue-on-error: true` is allowed

The repository deliberately limits this flag to four narrow contexts.
Anywhere else, it would mask a gate's failure and should be removed.

1. **SARIF upload to GitHub Security** (`reusable-iac-security.yaml`,
   `reusable-codeql.yaml`, `reusable-scorecard.yaml`) -- the *scan* is the
   gate and runs without `continue-on-error`. The upload step is
   best-effort because publishing to the Security tab requires GitHub
   Advanced Security on private repos. CodeQL disables the built-in upload
   and uploads the generated SARIF in a separate advisory step; findings
   remain visible in the run log and as workflow artifacts.
2. **Scorecard analysis on private repos** (`reusable-scorecard.yaml`) --
   Scorecard's GraphQL queries fail with *Resource not accessible by
   integration* on private repositories.
3. **Gitleaks advisory mode** (`reusable-iac-security.yaml`) -- caller-
   parameterised via `inputs.gitleaks_advisory`.
4. **Reusable validation lint advisory mode**
   (`reusable-terraform-validation.yaml`) -- caller-parameterised via
   `inputs.lint_advisory` for transition-only consumers. The lint jobs still
   run and report findings, but the contract and security gates remain
   blocking.

## Adding a new gate

1. Decide its role from the taxonomy above.
2. If the gate is reproducible locally, wire it through `tools/verify.py`
   so contributors can run it before pushing.
3. Add a row to the inventory table.
4. If blocking, ensure it appears in the repository's required status
   checks (branch protection on `main`).
5. Do not add `continue-on-error: true` outside the four contexts listed
   above without an explicit rationale in the workflow file.

## Negative-path discipline

This repository is the place where bad consumer inputs are most likely to
cause unsafe mutation, so every contract validator must be exercised by
both a `good/` fixture (must pass) and one or more `bad-*/` fixtures (must
fail with specific `[FAIL]` markers). See `tools/run_contract_tests.py`
and `tools/run_privileged_workflow_tests.py` for the pattern. New
validators added to `tools/check_*.py` should ship with matching fixtures
in `tests/fixtures/`.
