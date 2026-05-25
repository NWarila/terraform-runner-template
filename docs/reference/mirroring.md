# Mirroring And Consumer Baseline

This template keeps the serious controls in one place while keeping downstream
runner repos small enough to operate without ceremony.

## Required Consumer Baseline

A runner consumer must keep the contract-critical files: community health files,
`.github/CODEOWNERS`, Renovate config, `pr-validation.yaml`, `drift-gate.yaml`,
`security.yaml`, `terraform-deploy.yaml`, the docs skeleton, and the runner
inventory directories.

The contract validator checks the required paths and the caller-workflow wiring.
The template-tier drift manifest mirrors only the stable scaffold files that
should remain byte-identical across runners.

Use `byte_identical` only for files a downstream runner should keep
byte-for-byte with this template. Use `scaffold_starter` for template-maintainer
fixtures, local validation machinery, and starter inventory that prove the
pattern but should not become permanent mirrored content in data-only runner
repos. This runner template has more `scaffold_starter` entries than the
framework templates because consumers delegate tooling and policy execution to
the pinned reusable workflow instead of carrying local copies.

## Repo-Owned Layer

The runner owns `terraform/public/`, `terraform/private/`, deploy inputs, template pins,
framework pins, and repo-specific ADRs. Those files are validated for shape and
safety, not byte-mirrored.

## Optional Release Layer

`release.yaml`, release-please config, release evidence, and trusted-bot
auto-merge are supported by the template, but downstream runners do not have to
carry them. Keep that layer for repos that publish versioned releases. Remove it
for runners that only deploy inventory.

## Template-Maintainer Layer

The local contract validator, OPA policy tests, generated contract fixtures,
integration fixture, and `tools/verify.py` are template-maintainer machinery.
They are valuable in this template repo because `ci.yaml` executes them on
every PR, but they are not required in runner repos. Runner PRs exercise the
same controls through the pinned reusable validation workflow from this
template checkout.
Template-only self-validation workflows such as `ci.yaml` are not byte-mirrored
into consumers. The normal `terraform-deploy.yaml` caller is mirrored because it
is the regular runner deploy example: `pr-validation.yaml` plans locally, while
trusted main/manual deploy runs prove the S3 backend against the repo's actual
state key.

## New Runner Checklist

1. Rewrite `README.md` for the real runner.
2. Fill `terraform/public/` and configure how `terraform/private/` is sourced.
3. Pin `pr-validation.yaml` and `terraform-deploy.yaml` to the intended template
   and framework SHAs.
4. Decide whether to keep the optional release layer.
5. Run the runner's PR validation workflow, or run this template's
   `reusable-terraform-validation.yaml` from a scratch branch pinned to the
   candidate template SHA.
