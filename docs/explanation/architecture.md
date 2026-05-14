# Architecture

## Template boundary

`terraform-runner-template` is the type-template for Terraform-runner repos. It owns:

- The contract every Terraform-runner repo must satisfy ([`contract/runner-template-contract.yaml`](../../contract/runner-template-contract.yaml)).
- The runner-mode `pr-validation` reusable that checks out the consumed framework, overlays runner data, and runs the framework quality gate against the assembled tree ([`reusable-terraform-validation.yaml`](../../.github/workflows/reusable-terraform-validation.yaml) - framework-shaped validation belongs to framework templates).
- The canonical runner scaffold consumers adopt: shared tooling, OPA policy, reusable workflows, standard quality-gate callers, drift-gate layout, and the runner-specific deploy/validation wiring.
- The seed runner data and integration fixture that new runner repos inherit (`terraform/public/`, `terraform/private/`, `tests/fixtures/`, and `fixtures/integration/basic/`).
- The template-tier baseline manifest that every Terraform-runner consumer uses to mirror standardized scaffold files and template ADRs.

It does NOT own:

- An executable Terraform module of its own. Runners are data-only deployers: `terraform apply` runs against the framework's tree with the runner's `terraform/{public,private}` inventory overlaid onto the framework's `terraform/repos/` runtime path.
- A real Terraform module. The example consumer in this template's documentation points at [`NWarila/terraform-framework-template`](https://github.com/NWarila/terraform-framework-template) — a do-nothing reference framework used to validate the runner pattern end-to-end without external services.

## Inputs and outputs

A consumer runner pins to a SHA of this template. On adoption, the consumer:

- Inherits the standardized scaffold from `baseline-manifest.json`, then pins the runner-mode `pr-validation`, framework `terraform-deploy`, and drift-gate caller inputs to the appropriate template/framework SHAs.
- Drops in `terraform/public/`, `terraform/private/`, `tests/fixtures/` per the contract.

Renovate keeps both the `uses:` SHA on this template AND the `framework_ref` (the framework being deployed) in lockstep with their respective `main` branches.

## External dependencies

- [`NWarila/.github`](https://github.com/NWarila/.github) — provides org-baseline policy files, ADR masters, and documentation layout sentinels. Mirrored into this template and every consumer runner; verified by [`drift-gate`](https://github.com/NWarila/drift-gate) on every PR.
- The runner's framework being deployed (e.g. [`NWarila/terraform-framework-template`](https://github.com/NWarila/terraform-framework-template) for the do-nothing reference, or [`nwarila-platform/proxmox-terraform-framework`](https://github.com/nwarila-platform/proxmox-terraform-framework) for a real framework) — provides the `reusable-terraform-deploy` workflow runners call. The framework is outside this template's scope; consumer runners pin to it directly.
- [`NWarila/drift-gate`](https://github.com/NWarila/drift-gate) — composite GitHub Action invoked by every consumer's `drift-gate.yaml` workflow. SHA-pinned per ADR-0004's workflow-pinning rule.
