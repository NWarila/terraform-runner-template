# Invariants

Non-negotiable rules for this template. Violating one of these is a breaking change at minimum.

- **Org-owned policy files and `docs/decision-records/org/` mirrors are byte-identical with `NWarila/.github`.** `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `SECURITY.md`, `SUPPORT.md`, `LICENSE`, org ADRs, and layout sentinels are enforced on every PR by [`drift-gate.yaml`](../../.github/workflows/drift-gate.yaml) calling [`NWarila/drift-gate`](https://github.com/NWarila/drift-gate). Drift fails the workflow and surfaces inline annotations on the offending file in "Files changed".
- **Consumer runner scaffolds mirror only the stable baseline.** Stable workflow callers, shared reusable workflows used by those callers, layout sentinels, and formatting config are byte-identical across the class. Template-maintainer tooling, OPA tests, integration fixtures, template ADR copies, repo-specific inventory, framework pins, and deploy inputs are starter content or repo-owned content, not byte-compared.
- **The `runner` type is the only supported downstream consumer `repo_type`; `template` exists only for this repo's self-validation.** Framework-shape repos derive from a different reference (e.g. [`NWarila/terraform-framework-template`](https://github.com/NWarila/terraform-framework-template) for the do-nothing reference).
- **Framework-mode validation is not exposed here.** `mode: full` belongs to framework templates; this runner reusable accepts only `runner` and `contract-and-lint`.
- **Auto-merge never reads PR-controlled content under `pull_request_target`.** The reusable separates read-only author authorization from the write-token merge job, trusts only a closed bot list, and the OPA policy rejects checkout/PR-head references in `pull_request_target` workflows and the auto-merge reusable.
- **The `runner-mode` `reusable-terraform-validation` requires a pinned `framework_ref`.** Floating refs (`main`, branch names) defeat the end-to-end validation guarantee. Validated at job start by a regex check.
- **All `uses:` references are SHA-pinned to 40-character commit hashes** (or local `./...` references, or digest-pinned docker images). Tag/branch references are rejected by both the contract validator (`tools/check_template_contract.py`) and the OPA `repo_hygiene` policy.
- **Runners contain no executable Terraform module of their own.** Runners are data-only deployers per the contract's `runner` type; local inventory lives under `terraform/{public,private}` and is overlaid onto the framework's `terraform/repos/` runtime path at validation/deploy time.
- **Renovate keeps `uses:` SHAs and body ref inputs current.** GitHub Actions manager updates reusable workflow `uses:` pins; the custom `git-refs` regex manager updates `template_ref` and `framework_ref` SHA inputs. `tools/check_caller_workflows.py` now checks only that those refs are full SHAs.

## Template-Family Conventions

- Runner templates expose validation reusables as
  `reusable-<tool>-validation.yaml`, not
  `reusable-<tool>-framework-<verb>.yaml`. Frameworks own executable deploy
  behavior; runners validate inventory and caller shape.
- Runner `verify.py ci` keeps `contract-check` as a top-level target because
  contract validation is the template's central product surface. ADR schema is
  also explicit at the CI target level. `workflow-helper-tests` remains limited
  to workflow helper and privileged-workflow checks.
- Runner consumers do not own `verify.py`, OPA policy, contract fixtures, or
  reusable workflows of any kind. They call this template by immutable SHA.
  Auto-merge is centralized too: `auto-merge.yaml` is a thin caller of the
  org-owned `NWarila/.github/.github/workflows/reusable-auto-merge.yaml`,
  pinned by SHA, and the contract's `forbidden_paths` rejects any local
  `.github/workflows/reusable-*.yaml`. `pull_request_target` safety is enforced
  by the org `repo_hygiene` policy (run via the `repo-hygiene.yaml` caller),
  not by keeping the reusable local; the older "keep auto-merge local so the
  static analyzer sees the full call graph" rationale predates centralized
  `repo_hygiene` and is superseded.
