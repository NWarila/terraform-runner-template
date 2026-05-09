# Invariants

Non-negotiable rules for this template. Violating one of these is a breaking change at minimum.

- **`docs/decision-records/org/` mirrors are byte-identical with `nwarila-platform/.github`.** Enforced on every PR by [`drift-gate.yaml`](../../.github/workflows/drift-gate.yaml) calling [`NWarila/drift-gate`](https://github.com/NWarila/drift-gate). Drift fails the workflow and surfaces inline annotations on the offending file in "Files changed".
- **The `runner` type is the only supported `repo_type`.** Adding a framework or other type to this template is out of scope; framework-shape repos derive from a different reference (e.g. [`NWarila/terraform-framework-template`](https://github.com/NWarila/terraform-framework-template) for the do-nothing reference).
- **The `runner-mode` `reusable-terraform-validation` requires a pinned `framework_ref`.** Floating refs (`main`, branch names) defeat the end-to-end validation guarantee. Validated at job start by a regex check.
- **All `uses:` references are SHA-pinned to 40-character commit hashes** (or local `./...` references, or digest-pinned docker images). Tag/branch references are rejected by both the contract validator (`tools/check_template_contract.py`) and the OPA `golden_terraform` policy.
- **Runners contain no `terraform/` directory of their own.** Runners are data-only deployers per the contract's `runner` type; `terraform apply` runs against the framework's tree with the runner's `repos/` data overlaid at validation/deploy time.
- **Renovate keeps `uses:` SHAs and `framework_ref` inputs in lockstep.** The `template_ref` and the `framework_ref` must always match each other where they refer to the same repo; Renovate's regex manager handles this.
