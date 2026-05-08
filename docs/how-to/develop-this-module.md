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
yamllint .github/workflows/ contract/ sync/

# Smoke-test the contract validator + seed_consumer
python tools/check_template_contract.py --help
python tools/seed_consumer.py --help

# Run zizmor against workflows
zizmor --persona regular .github/workflows/
```

## Editing universal-layer files

Files listed in `sync/canonical-baseline.yaml` come from canonical
(`terraform-template-template`). To change one of them:

1. Land the change in `terraform-template-template/main` first.
2. Bump this template's `CANONICAL_REF` in
   `.github/workflows/canonical-baseline-sync.yaml` (Renovate does this
   automatically on schedule).
3. The sync workflow opens a PR pulling the new content here. Merge it.

If you need a per-template-specific override of a universal file, REMOVE
its entry from `sync/canonical-baseline.yaml` first; otherwise the next
sync run reverts your local change.

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
