# Architecture

## Template boundary

`terraform-runner-template` is the type-template for Terraform-runner repos. It owns:

- The contract every Terraform-runner repo must satisfy ([`contract/runner-template-contract.yaml`](../../contract/runner-template-contract.yaml)).
- The runner-mode `pr-validation` reusable that checks out the consumed framework, overlays runner data, and runs `make ci` against the assembled tree ([`reusable-terraform-validation.yaml`](../../.github/workflows/reusable-terraform-validation.yaml) — only the runner mode is exercised in this template).
- The canonical caller-workflow set runners adopt: `pr-validation`, `terraform-deploy` (calls the framework's deploy reusable directly), `drift-gate` (org-tier byte-equality), plus the universal quality-gate set (codeql, scorecard, security, auto-merge, release-please, release-evidence).
- The seed scaffold that [`tools/seed_consumer.py --type runner`](../../tools/seed_consumer.py) generates for new runner repos.
- The template-tier ADRs that every Terraform-runner consumer mirrors at `docs/decision-records/template/`.

It does NOT own:

- A `terraform/` directory of its own. Runners are data-only deployers — `terraform apply` runs against the framework's tree with the runner's `repos/` data overlaid on top.
- A real Terraform module. The example consumer in this template's documentation points at [`NWarila/terraform-framework-template`](https://github.com/NWarila/terraform-framework-template) — a do-nothing reference framework used to validate the runner pattern end-to-end without external services.

## Inputs and outputs

A consumer runner pins to a SHA of this template. On adoption, the consumer:

- Adds the canonical caller-workflow set (this template's runner-mode `pr-validation` + the universal reusables, plus the framework's `terraform-deploy` and a `drift-gate` caller).
- Drops in `repos/public/`, `repos/private/`, `tests/fixtures/` per the contract.
- Declares `.template-type=runner` so the contract validator infers shape correctly.

Renovate keeps both the `uses:` SHA on this template AND the `framework_ref` (the framework being deployed) in lockstep with their respective `main` branches.

## External dependencies

- [`nwarila-platform/.github`](https://github.com/nwarila-platform/.github) — provides org-baseline ADR masters. Mirrored into this template's `docs/decision-records/org/` and into every consumer runner's same path; verified by [`drift-gate`](https://github.com/NWarila/drift-gate) on every PR.
- The runner's framework being deployed (e.g. [`NWarila/terraform-framework-template`](https://github.com/NWarila/terraform-framework-template) for the do-nothing reference, or [`nwarila-platform/proxmox-terraform-framework`](https://github.com/nwarila-platform/proxmox-terraform-framework) for a real framework) — provides the `reusable-terraform-deploy` workflow runners call. The framework is outside this template's scope; consumer runners pin to it directly.
- [`NWarila/drift-gate`](https://github.com/NWarila/drift-gate) — composite GitHub Action invoked by every consumer's `drift-gate.yaml` workflow. SHA-pinned per ADR-0004's workflow-pinning rule.
