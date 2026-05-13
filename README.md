# terraform-runner-template

A template for Terraform repos that consume a framework: they own data (the
inputs that describe what to deploy) but not the Terraform module itself. Use it
to scaffold a new runner repo with CI, policy, drift-gate, and release evidence
already wired up.

A *fleet* of repositories is only as rigorous as its worst member. The
per-type-template family moves the rigor — workflows, policies, contract — into
one place per type that every consumer of that type references by SHA. When the
standard improves here, every runner gets the improvement on its next dependency
bump. When a runner drifts, the contract validator catches it on the next PR.

## Quickstart

```sh
make help
make setup
python tools/verify.py ci
python tools/verify.py integration --framework-source ../terraform-framework-template/terraform
```

For a real runner derived from this template, update `repos/public/`, the private inventory source, `.github/workflows/pr-validation.yaml`, `.github/workflows/terraform-deploy.yaml`, and any repo-local decisions under `docs/decision-records/repo/`. The mirroring rules live in [`docs/reference/mirroring.md`](docs/reference/mirroring.md); AWS bootstrap expectations live in [`docs/reference/aws-bootstrap-requirements.md`](docs/reference/aws-bootstrap-requirements.md).

## Normalized repo interface

This repo uses the same validation command surface as the Terraform framework template:

| Command | Purpose |
| --- | --- |
| `make lint` | Repo-local static checks: Python tooling and workflow/contract YAML. |
| `make policy` | OPA policy tests plus policy evaluation against real repo files. |
| `make docs-check` | Diátaxis/ADR documentation layout check. |
| `python tools/verify.py ci` | Repo-local quality gate. |
| `python tools/verify.py integration` | Ephemeral consumer workspace assembled from this runner fixture plus a framework checkout. |
| `python tools/verify.py verify` | Full local verification: `ci` plus `integration`. |

Runner integration expects the framework template beside this repo by default:

```sh
python tools/verify.py integration
# or override the framework module path
python tools/verify.py integration --framework-source ../terraform-framework-template/terraform
```

The shared CI harness lives in `tools/ci/`; the runner-specific fixture lives in `fixtures/integration/basic/`. That mirrors the framework repo's shape while preserving the rule that runners do not own a top-level `terraform/` directory.

## What this template provides

| Surface | Mechanism | What it enforces |
| --- | --- | --- |
| Reusable validation | [`reusable-terraform-validation.yaml`](.github/workflows/reusable-terraform-validation.yaml) (`mode: runner`) | Checks out the framework at `framework_ref`, overlays runner data, runs the framework quality gate against the assembled tree. |
| Drift gate | [`drift-gate.yaml`](.github/workflows/drift-gate.yaml) + [`baseline-manifest.json`](baseline-manifest.json) | Pinned [`NWarila/drift-gate`](https://github.com/NWarila/drift-gate) verifies org-baseline mirrors here and gives consumers a template-tier manifest for byte-identical runner scaffold files. |
| Contract validator | [`tools/check_template_contract.py`](tools/check_template_contract.py) | Required files, paths, and content rules for runner repos. |
| Contract manifest | [`contract/runner-template-contract.yaml`](contract/runner-template-contract.yaml) | Single machine-readable source of truth. |
| Universal quality gates | `security.yaml`, optional `release.yaml`, and reusable workflows | Security tooling is part of the required baseline; release tooling is available for repos that publish versions. |

## How a consumer adopts this template

Each consuming runner repository inherits the standardized scaffold from this
template, then pins the load-bearing caller workflows to explicit SHAs:

```yaml
# .github/workflows/pr-validation.yaml
jobs:
  validate:
    uses: NWarila/terraform-runner-template/.github/workflows/reusable-terraform-validation.yaml@<40-char-sha>
    with:
      mode: runner
      framework_repo: NWarila/terraform-framework-template
      framework_ref: <pinned-framework-sha>
      overlay_paths: |
        repos/public => terraform/repos/public
        tests/fixtures/repos/private => terraform/repos/private
      # ...tool versions...
```

```yaml
# .github/workflows/terraform-deploy.yaml
on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read

jobs:
  deploy:
    permissions:
      contents: read
      id-token: write
    uses: NWarila/terraform-framework-template/.github/workflows/reusable-terraform-deploy.yaml@<40-char-sha>
    with:
      framework_ref: <pinned-framework-sha>
      overlay_paths: |
        repos/public => terraform/repos/public
      backend_mode: s3
      backend_key_prefix: <reviewed-state-prefix>
      upload_plan_artifact: false
      apply: true
    secrets:
      aws_role_arn: ${{ secrets.AWS_DEPLOY_ROLE_ARN }}
      aws_region: ${{ secrets.AWS_REGION }}
      backend_bucket: ${{ secrets.TF_BACKEND_BUCKET }}
```

Overlay paths are always copied as directory contents when the source is a
directory. A trailing slash is accepted for readability but has no separate
meaning; `repos/public` and `repos/public/` behave the same way.

Renovate keeps both the `uses:` SHAs and the `framework_ref` inputs current.
The runner's `pr-validation.yaml` handles credential-free pull request
validation. The runner's `terraform-deploy.yaml` is the trusted deploy path:
it calls the framework's `reusable-terraform-deploy.yaml` with repo-specific
S3 backend and OIDC settings from reviewed inputs and repository or environment
secrets.

## Architecture

This template participates in the three-tier ADR model formalised in [`NWarila/.github` ADR-0001](docs/decision-records/org/0001-use-architecture-decision-records.md):

- **Org tier** — ADRs apply to every repo in the portfolio regardless of stack. Mirrored at [`docs/decision-records/org/`](docs/decision-records/org/) byte-identical with [`NWarila/.github`](https://github.com/NWarila/.github). Drift-gated.
- **Template tier** — ADRs apply to every Terraform-runner consumer derived from this template. Master copies live at [`docs/decision-records/template/`](docs/decision-records/template/); first ADR is [`template/0001-pin-terraform-and-provider-versions-exactly.md`](docs/decision-records/template/0001-pin-terraform-and-provider-versions-exactly.md).
- **Repo tier** — ADRs specific to one consumer repo, in that consumer's [`docs/decision-records/repo/`](docs/decision-records/repo/).

## Versioning

Conventional Commits + release-please. Consumers pin to commit SHAs (per the same rule the contract enforces on them) and let Renovate carry pins forward.
