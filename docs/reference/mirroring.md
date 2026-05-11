# Mirroring And Consumer Baseline

This template keeps the serious controls in one place while keeping downstream
runner repos small enough to operate without ceremony.

## Required Consumer Baseline

A runner consumer must keep the contract-critical files: community health files,
`.github/CODEOWNERS`, Renovate config, `pr-validation.yaml`, `drift-gate.yaml`,
`security.yaml`, `terraform-deploy.yaml`, the docs skeleton, `Makefile`,
`tools/verify.py`, and the runner inventory directories.

The contract validator checks the required paths and the caller-workflow wiring.
The template-tier drift manifest mirrors only the stable scaffold files that
should remain byte-identical across runners.

## Repo-Owned Layer

The runner owns `repos/public/`, `repos/private/`, deploy inputs, template pins,
framework pins, and repo-specific ADRs. Those files are validated for shape and
safety, not byte-mirrored.

## Optional Release Layer

`release.yaml`, release-please config, release evidence, and trusted-bot
auto-merge are supported by the template, but downstream runners do not have to
carry them. Keep that layer for repos that publish versioned releases. Remove it
for runners that only deploy inventory.

## Template-Maintainer Layer

Reusable workflows, OPA policy tests, generated contract fixtures, and contract
tooling are template-maintainer machinery. They are valuable portfolio signal,
but new runner repos should only touch them when changing the baseline itself.

## New Runner Checklist

1. Rewrite `README.md` for the real runner.
2. Fill `repos/public/` and configure how `repos/private/` is sourced.
3. Pin `pr-validation.yaml` and `terraform-deploy.yaml` to the intended template
   and framework SHAs.
4. Decide whether to keep the optional release layer.
5. Run `python tools/verify.py verify`.
