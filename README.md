# terraform-runner-template

The opinionated template for **terraform-runner** repositories under any
NWarila-owned organization (NWarila, nwarila-platform, the-hero-wars-guys, …).

A *runner* is a data-only deployer: it owns an inventory of repository
definitions in `repos/public/` and `repos/private/` (the latter typically
fetched from S3 at deploy time) and delegates the actual `terraform apply`
to a Terraform framework reusable workflow. Runners contain no Terraform
module code of their own.

This template provides the contract every runner must conform to,
the reusable PR validation in `mode: runner`, and the canonical caller
workflow set. It is one of seven per-type templates in the
[NWarila template family](https://github.com/NWarila):

| Template | Repo type |
| --- | --- |
| [`terraform-template-template`](https://github.com/NWarila/terraform-template-template) | Canonical/baseline + terraform-framework |
| **`terraform-runner-template`** | **terraform-runner (this template)** |
| `python-template` | Python projects |
| `powershell-template` | PowerShell modules |
| `packer-template` | Packer image builders |
| `bash-template` | Bash script collections |
| `generic-template` | Anything else |

## What this template provides

| Surface | Mechanism | What it enforces |
| --- | --- | --- |
| Reusable validation | `reusable-terraform-validation.yaml` (mode: runner) | Checks out the framework at `framework_ref`, overlays runner data, runs `make ci` against the assembled tree. |
| Canonical baseline sync | `canonical-baseline-sync.yaml` | Daily PR keeping universal reusables byte-identical with `terraform-template-template`. |
| Contract validator | `tools/check_template_contract.py` | Required files, paths, and content rules for runner repos. |
| Contract manifest | `contract/runner-template-contract.yaml` | Single machine-readable source of truth. |
| Universal quality gates | 8 reusable workflows | codeql, scorecard, iac-security, auto-merge, org-adr-sync, release-please, release-evidence, template-sync. |

## How a consumer adopts this template

Each consuming runner repository declares `.template-type=runner` and adds
the canonical caller-workflow set with `uses:` lines pinned to a
40-character SHA of this template:

```yaml
# .github/workflows/pr-validation.yaml
jobs:
  validate:
    uses: NWarila/terraform-runner-template/.github/workflows/reusable-terraform-validation.yaml@<40-char-sha>
    with:
      mode: runner
      framework_repo: nwarila-platform/github-terraform-framework
      framework_ref: <pinned-framework-sha>
      overlay_paths: |
        repos/public/=>terraform/repos/public/
        tests/fixtures/repos/private/=>terraform/repos/private/
      # ...tool versions...
```

Renovate keeps both the `uses:` SHA and the `framework_ref` input current.
The runner's `terraform-deploy.yaml` calls the framework's
`reusable-terraform-deploy.yaml` directly, with per-runner specifics in
repo Variables and Secrets.

## Versioning

This repository uses Conventional Commits and release-please. Consumers
pin to commit SHAs (per the same rule the contract enforces on them) and
let Renovate carry pins forward.

## Why this exists

A *fleet* of repositories is only as rigorous as its worst member. The
per-type-template family moves the rigor — workflows, policies, contract —
into one place per type that every consumer of that type references by SHA.
When the standard improves here, every runner gets the improvement on its
next dependency bump. When a runner drifts, the contract validator catches
it on the next PR.
