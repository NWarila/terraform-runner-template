# Develop this template

## Local setup

This template doesn't ship Terraform code itself — it's a meta-repo. Use
the same tooling consumer runners use:

- Terraform 1.15.1 (only needed if you're running cross-template sync
  validation locally; the template doesn't run terraform itself).
- Python 3.12 with `pyyaml`, `ruff`, `yamllint`, `zizmor`.
- `markdownlint-cli2` (via npm or the action).

## The development loop

```sh
# Lint the Python tools
ruff check tools/

# Lint the workflows
yamllint .github/workflows/ contract/

# Smoke-test the contract validator + seed_consumer
python tools/check_template_contract.py --help
python tools/seed_consumer.py --help

# Run zizmor against workflows
zizmor --persona regular .github/workflows/
```

## Editing org-baseline-mirrored files

Org-baseline ADRs at `docs/decision-records/org/` are byte-mirrored from
`nwarila-platform/.github`. Edits to those files would fail
[`drift-gate.yaml`](../../.github/workflows/drift-gate.yaml) on the next
PR. To change the content of an org-baseline ADR:

1. Land the change in `nwarila-platform/.github/main` first.
2. Bump the `source-ref` SHA in this template's
   [`drift-gate.yaml`](../../.github/workflows/drift-gate.yaml) (Renovate
   does this automatically as the canonical advances).
3. Resync the mirrored content here in the same PR (copy the canonical
   file to `docs/decision-records/org/...`).

Drift-gate will catch any divergence between this template's mirrors
and the canonical at the pinned `source-ref`.

## Editing type-specific files

The contract (`contract/runner-template-contract.yaml`), the runner-mode
of `reusable-terraform-validation.yaml`, the seed scaffold in
`tools/seed_consumer.py`'s `RUNNER_SEEDS`, and per-template docs are
owned solely by this template. Changes land here and propagate to
consumer runners via their own pin bumps (Renovate-managed).

## Before opening a PR

Self-CI runs the same gates above; if they pass locally, CI will pass.
Branch protection on `main` requires all status checks green before
merge.
