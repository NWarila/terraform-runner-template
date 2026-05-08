# Architecture

## Template boundary

`terraform-runner-template` is one of seven per-type templates in the
NWarila template family. It owns:

- The contract that every terraform-runner repo must satisfy
  (`contract/runner-template-contract.yaml`).
- The runner-mode `pr-validation` reusable that checks out the consumed
  framework, overlays runner data, and runs `make ci` against the
  assembled tree (`reusable-terraform-validation.yaml` shared with
  `terraform-template-template`; the runner mode is what's exercised here).
- The canonical caller workflow set runners adopt: `pr-validation`,
  `terraform-deploy` (calls the framework's deploy reusable), plus the
  universal quality-gate set (codeql, scorecard, security, auto-merge,
  org-adr-sync, release-please, release-evidence, template-sync).
- The seed scaffold that `tools/seed_consumer.py --type runner`
  generates for new runner repos.

It does NOT own (canonical-baseline-sync pulls these from
`terraform-template-template`):

- The 8 universal reusable workflows.
- The toolchain configs (`.editorconfig`, `.gitattributes`,
  `.markdownlint-cli2.jsonc`, `.pre-commit-config.yaml`,
  `.terraform-docs.yml`, `.tflint.hcl`, `Makefile`).
- The shared tools (`tools/check_docs_layout.py`,
  `tools/install_ci_tools.sh`).
- The Renovate baseline.

## Inputs and outputs

A consumer runner pins to a SHA of this template. On adoption, the
consumer:

- Adds 9 caller workflows (the universal 8 + this template's
  type-specific `pr-validation` and runner-only `terraform-deploy`).
- Drops in `repos/public/`, `repos/private/`, `tests/fixtures/` per the
  contract.
- Declares `.template-type=runner` so the contract validator infers
  shape correctly.

Renovate keeps both the `uses:` SHA on this template AND the
`framework_ref` (the framework being deployed) in lockstep with their
respective `main` branches.

## External dependencies

- `NWarila/terraform-template-template` — canonical source for the
  universal layer. Synced via `canonical-baseline-sync.yaml`.
- The runner's framework being deployed (e.g.
  `nwarila-platform/github-terraform-framework`) — provides the
  `reusable-terraform-deploy` workflow runners call. The framework is
  outside this template's scope; consumer runners pin to it directly.
- `<owner>/.github` — provides org-baseline ADR masters. Mirrored into
  this template's `docs/decision-records/org/` and into every consumer
  runner's same path; verified by the universal `org-adr-sync` workflow.
