# terraform-runner-template

The opinionated template for **terraform-runner** repositories under any NWarila-owned organization (`NWarila`, `nwarila-platform`, `the-hero-wars-guys`, …).

A *runner* is a data-only deployer: it owns an inventory of repository definitions in `repos/public/` and `repos/private/` (the latter typically fetched from S3 at deploy time) and delegates the actual `terraform apply` to a Terraform framework's reusable workflow. **Runners contain no `terraform/` directory of their own** — that's the framework's job.

This template provides the contract every runner must satisfy plus the canonical caller-workflow set.

## What this template provides

| Surface | Mechanism | What it enforces |
| --- | --- | --- |
| Reusable validation | [`reusable-terraform-validation.yaml`](.github/workflows/reusable-terraform-validation.yaml) (`mode: runner`) | Checks out the framework at `framework_ref`, overlays runner data, runs `make ci` against the assembled tree. |
| Drift gate | [`drift-gate.yaml`](.github/workflows/drift-gate.yaml) | Pinned [`NWarila/drift-gate`](https://github.com/NWarila/drift-gate) composite action verifies this template's mirrored copies of org-baseline files are byte-identical to canonical. Replaces the previous `org-adr-sync` + `template-sync` mechanisms with a single composable check. |
| Contract validator | [`tools/check_template_contract.py`](tools/check_template_contract.py) | Required files, paths, and content rules for runner repos. |
| Contract manifest | [`contract/runner-template-contract.yaml`](contract/runner-template-contract.yaml) | Single machine-readable source of truth. |
| Universal quality gates | Reusable workflows for codeql, scorecard, iac-security, auto-merge, release-please, release-evidence | Universal lint/security/release tooling consumers wire up via `uses:` lines pinned to this template's SHA. |

## How a consumer adopts this template

Each consuming runner repository declares `.template-type=runner` and adds the canonical caller workflow set with `uses:` lines pinned to a 40-character SHA of this template:

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
        repos/public/=>terraform/repos/public/
        tests/fixtures/repos/private/=>terraform/repos/private/
      # ...tool versions...
```

```yaml
# .github/workflows/terraform-deploy.yaml
jobs:
  deploy:
    uses: NWarila/terraform-framework-template/.github/workflows/reusable-terraform-deploy.yaml@<40-char-sha>
    with:
      framework_ref: <pinned-framework-sha>
      overlay_paths: |
        repos/public/=>terraform/repos/public/
      apply: ${{ github.ref == 'refs/heads/main' }}
```

Renovate keeps both the `uses:` SHAs and the `framework_ref` inputs current. The runner's `terraform-deploy.yaml` calls the framework's `reusable-terraform-deploy.yaml` with per-runner specifics in repo Variables and Secrets.

## Architecture

This template participates in the three-tier ADR model formalised in [`nwarila-platform/.github` ADR-0001](docs/decision-records/org/0001-use-architecture-decision-records.md):

- **Org tier** — ADRs apply to every repo in the portfolio regardless of stack. Mirrored at [`docs/decision-records/org/`](docs/decision-records/org/) byte-identical with [`nwarila-platform/.github`](https://github.com/nwarila-platform/.github). Drift-gated.
- **Template tier** — ADRs apply to every Terraform-runner consumer derived from this template. Master copies live at [`docs/decision-records/`](docs/decision-records/); first ADR is [`template/0001-pin-terraform-and-provider-versions-exactly.md`](docs/decision-records/0001-pin-terraform-and-provider-versions-exactly.md).
- **Repo tier** — ADRs specific to one consumer repo, in that consumer's [`docs/decision-records/repo/`](docs/decision-records/repo/).

## Versioning

Conventional Commits + release-please. Consumers pin to commit SHAs (per the same rule the contract enforces on them) and let Renovate carry pins forward.

## Why this exists

A *fleet* of repositories is only as rigorous as its worst member. The per-type-template family moves the rigor — workflows, policies, contract — into one place per type that every consumer of that type references by SHA. When the standard improves here, every runner gets the improvement on its next dependency bump. When a runner drifts, the contract validator catches it on the next PR.
