#!/usr/bin/env python3
"""DEPRECATED — scaffold contents reference retired workflows.

This tool currently scaffolds `template-sync.yaml` and `org-adr-sync.yaml`
caller workflows whose reusables were retired when this template adopted
`NWarila/drift-gate`. New consumer scaffolds produced by this tool would
fail their first PR. Rewrite needed before next use.

Scaffold golden-template contract structure in a new consumer repo.

Usage:
    cd /path/to/consumer/repo
    python /path/to/terraform-template/tools/seed_consumer.py --type framework
    python /path/to/terraform-template/tools/seed_consumer.py --type runner

Idempotent. Creates files only when they don't exist; never overwrites.

Two repo shapes are supported (same shapes the contract validator enforces):

  framework — Self-contained Terraform module. Seeds terraform/, examples/,
              docs/, etc.
  runner    — Data-only deployer. Seeds repos/{public,private}/,
              tests/fixtures/, docs/, etc. Does NOT seed terraform/.

Both shapes get a `.template-type` file at the repo root so subsequent
contract-validator runs don't have to infer.

Files this script seeds (UNIVERSAL):
    docs/README.md
    docs/explanation/{architecture,testing-strategy,threat-model}.md
    docs/reference/{release-gates,invariants}.md
    docs/how-to/develop-this-module.md
    docs/decision-records/README.md
    policies/opa/.gitkeep
    .release-please-manifest.json
    release-please-config.json
    CHANGELOG.md
    .github/CODEOWNERS
    .github/PULL_REQUEST_TEMPLATE.md
    .template-type
    .gitignore (deny-all baseline if absent)

Framework-only seeds:
    terraform/{versions,variables,locals,resources,outputs}.tf
    terraform/tests/.gitkeep
    docs/reference/terraform.md
    examples/minimal/main.tf
    examples/minimal/README.md

Runner-only seeds:
    repos/public/.gitkeep
    repos/private/.gitkeep
    tests/fixtures/repos/public/example.yml
    tests/fixtures/repos/private/example.yml

Files kept in sync by tools/template-sync (not seeded here):
    .editorconfig, .gitattributes, .terraform-docs.yml, .tflint.hcl,
    .pre-commit-config.yaml, .markdownlint-cli2.jsonc, Makefile,
    tools/check_docs_layout.py, .github/renovate.json5

After running this seed, the consumer's first sync run after the next
template SHA bump will fill in the synced files. The consumer is then
contract-conformant and can adopt the reusable validation workflow.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


VALID_TYPES = ("framework", "runner")


# ---------------------------------------------------------------------------
# Universal stub content — applies to both repo types.
# ---------------------------------------------------------------------------

DOCS_README = '''# Documentation

Documentation for this repository follows the [Diátaxis framework](https://diataxis.fr/)
per [org ADR-0002](decision-records/org/0002-adopt-diataxis-documentation-framework.md).

| Quadrant     | Path                  | Purpose                              |
| ------------ | --------------------- | ------------------------------------ |
| Explanation  | `explanation/`        | Architecture, threat model, testing  |
| Reference    | `reference/`          | Generated terraform docs, invariants |
| How-to       | `how-to/`             | Task-oriented guides                 |
| Decisions    | `decision-records/`   | ADRs (org-mirrored + repo-specific)  |
'''

ARCHITECTURE_MD = '''# Architecture

## Module boundary

Describe what this module owns and what consumers must provide.

## Inputs and outputs

Summarize the variable surface and the output surface.

## External dependencies

List external systems this module talks to and the trust assumptions made
about each.
'''

TESTING_STRATEGY_MD = '''# Testing Strategy

## What the tests cover

Describe the layers exercised by `terraform test` and what each layer
proves.

## What the tests do NOT cover

Be explicit. Document the gap between unit-level coverage and
integration/staging coverage so reviewers know what they are accepting.
'''

THREAT_MODEL_MD = '''# Threat Model

## Scope

What this module guarantees:

- TODO

## Out of scope

What this module does **not** guarantee:

- TODO

Cross-reference: `SECURITY.md` (in `nwarila/.github` or
`nwarila-platform/.github`) defines the org-level reporting channel and
the org-wide scope boundary.
'''

RELEASE_GATES_MD = '''# Release Gates

PRs to `main` must pass:

- `make ci` (Terraform fmt/init/validate/test, TFLint, terraform-docs
  diff, Diátaxis docs layout, OPA tests)
- Reusable lint gates (actionlint, shellcheck, yamllint, ruff,
  markdownlint)
- Reusable IaC security gates (Trivy, Gitleaks, zizmor)

All gates run via `NWarila/terraform-template` reusable workflows and
must be SHA-pinned per the contract.
'''

INVARIANTS_MD = '''# Invariants

Non-negotiable rules for this module. Violating one of these is a
breaking change at minimum.

- TODO: enumerate invariants. Examples:
  - "Outputs MUST remain stable across patch versions."
  - "Resources MUST verify external content via SHA-256 before consuming."
'''

HOWTO_DEVELOP_MD = '''# Develop this module

## Local setup

Use the devcontainer in [`nwarila/terraform-template/.devcontainer`](https://github.com/NWarila/terraform-template/tree/main/.devcontainer)
or install the same pinned tools manually:

- Terraform 1.15.1
- TFLint 0.59.1
- terraform-docs 0.20.0
- OPA 1.10.0
- Python 3.12 with `pyyaml`, `ruff`, `yamllint`, `zizmor`

## The development loop

```sh
make fmt        # format Terraform
make ci         # run every gate
make docs       # regenerate docs/reference/terraform.md
```

## Before opening a PR

```sh
make ci
```

If `make ci` is green locally, the reusable validation workflow will be
green in CI.
'''

DECISION_RECORDS_README = '''# Architecture Decision Records

This directory contains the Architecture Decision Records (ADRs) for this
repository.

ADRs are organized into two scopes per
[org ADR-0001](https://github.com/nwarila-platform/.github/blob/main/docs/decision-records/0001-use-architecture-decision-records.md):

- `org/` — byte-identical mirrors of org-baseline ADRs.
- `repo/` — repository-specific ADRs.

When this repo gains its first decision, copy the org ADR-0001 file as
the ADR template and place new entries in `repo/NNNN-short-kebab-title.md`.
'''

CHANGELOG_MD = '''# Changelog

Generated by release-please. Do not edit by hand.
'''

RELEASE_PLEASE_MANIFEST = '''{
  ".": "0.0.0"
}
'''

RELEASE_PLEASE_CONFIG = '''{
  "$schema": "https://raw.githubusercontent.com/googleapis/release-please/main/schemas/config.json",
  "release-type": "terraform-module",
  "bootstrap-sha": "0000000000000000000000000000000000000000",
  "include-component-in-tag": false,
  "include-v-in-tag": true,
  "packages": {
    ".": {
      "package-name": "",
      "changelog-path": "CHANGELOG.md"
    }
  }
}
'''

CODEOWNERS = '''# Default owner for all files.
* @NWarila
'''

PR_TEMPLATE = '''## Summary

<!-- 1-3 bullets describing what this PR changes and why. -->

## Risk

<!-- What could break? What did you test? Reference any incident drills. -->

## Test plan

- [ ] `make ci` passes locally
- [ ] PR Validation green in CI
- [ ] Security Scan green in CI
- [ ] Documentation reflects the change (when applicable)
'''


# ---------------------------------------------------------------------------
# Framework-only stubs.
# ---------------------------------------------------------------------------

VERSIONS_TF = '''terraform {
  # Pin Terraform exactly per org ADR 0005.
  required_version = "= 1.15.1"

  required_providers {
    # Add provider blocks here. Each must use exact `=` pinning.
    # Example:
    #   proxmox = {
    #     source  = "bpg/proxmox"
    #     version = "= 0.50.0"
    #   }
  }
}
'''

VARIABLES_TF = '''# Module inputs.
#
# Every variable MUST set `nullable = false` for required inputs and include
# a `validation` block when the input has constraints beyond its type.
'''

LOCALS_TF = '''# Normalized internal values derived from variables.
#
# Avoid duplicating logic between resources. If a value is referenced in two
# or more places, name it here.

locals {}
'''

RESOURCES_TF = '''# Managed resources for this module.
#
# Keep resource definitions minimal and explicit. Surface dangerous toggles
# through input variables with safe defaults; never hardcode credentials.
'''

OUTPUTS_TF = '''# Stable outputs.
#
# Outputs form the module's public contract. Removing or renaming an output
# is a breaking change.
'''

REFERENCE_TERRAFORM_MD = '''# Terraform Reference

This file is overwritten by `terraform-docs` on every PR via the
`docs-diff` gate. Do not edit by hand between the markers below.

<!-- BEGIN_TF_DOCS -->
<!-- END_TF_DOCS -->
'''

EXAMPLE_MAIN_TF = '''# Minimal example consumer for this module.
#
# Used by pr-validation to prove the module is end-to-end consumable. When
# a runner repo bumps this framework's SHA, this example is what proves the
# framework still works.

terraform {
  required_version = "= 1.15.1"
}

# TODO: instantiate the module under ../../terraform with realistic inputs.
# module "example" {
#   source = "../../terraform"
#
#   # ...required inputs...
# }
'''

EXAMPLE_README_MD = '''# Minimal example

The smallest viable consumer of this module. Used by `pr-validation` as a
fixture for end-to-end validation.

```sh
cd examples/minimal
terraform init
terraform plan
```
'''


# ---------------------------------------------------------------------------
# Runner-only stubs.
# ---------------------------------------------------------------------------

RUNNER_FIXTURE_PUBLIC = '''# Public-safe fixture used by pr-validation only.
# In production, this directory is populated from the runner's repos/public/.
name: example-public-repo
visibility: public
'''

RUNNER_FIXTURE_PRIVATE = '''# Public-safe fixture used by pr-validation only.
# In production, the actual private repo definitions are sourced from S3.
# Anything sensitive must NOT live here — this file is in the public repo.
name: example-private-repo
visibility: private
'''


# ---------------------------------------------------------------------------
# .gitignore deny-all baselines.
# ---------------------------------------------------------------------------

GITIGNORE_FRAMEWORK = '''# Deny-all .gitignore strategy per org ADR-0003.
# Anything not explicitly allowlisted below is ignored.
**

# Core repo files
!.editorconfig
!.gitattributes
!.gitignore
!.markdownlint-cli2.jsonc
!.pre-commit-config.yaml
!.terraform-docs.yml
!.tflint.hcl
!.template-type
!CHANGELOG.md
!LICENSE
!Makefile
!README.md
!release-please-config.json
!.release-please-manifest.json

# GitHub configuration
!/.github/
!/.github/CODEOWNERS
!/.github/PULL_REQUEST_TEMPLATE.md
!/.github/renovate.json5
!/.github/workflows/
!/.github/workflows/pr-validation.yaml
!/.github/workflows/security.yaml
!/.github/workflows/template-sync.yaml
!/.github/workflows/codeql.yaml
!/.github/workflows/scorecard.yaml
!/.github/workflows/release-please.yaml
!/.github/workflows/auto-merge.yaml

# Terraform module sources, examples, and tests
!/terraform/
!/terraform/locals.tf
!/terraform/outputs.tf
!/terraform/resources.tf
!/terraform/variables.tf
!/terraform/versions.tf
!/terraform/tests/
!/terraform/tests/.gitkeep
!/examples/
!/examples/**

# Documentation (Diátaxis)
!/docs/
!/docs/README.md
!/docs/explanation/
!/docs/explanation/architecture.md
!/docs/explanation/testing-strategy.md
!/docs/explanation/threat-model.md
!/docs/reference/
!/docs/reference/invariants.md
!/docs/reference/release-gates.md
!/docs/reference/terraform.md
!/docs/how-to/
!/docs/how-to/develop-this-module.md
!/docs/decision-records/
!/docs/decision-records/README.md

# Tools
!/tools/
!/tools/check_docs_layout.py

# Policies
!/policies/
!/policies/opa/
!/policies/opa/.gitkeep
'''

GITIGNORE_RUNNER = '''# Deny-all .gitignore strategy per org ADR-0003.
# Anything not explicitly allowlisted below is ignored.
**

# Core repo files
!.editorconfig
!.gitattributes
!.gitignore
!.markdownlint-cli2.jsonc
!.pre-commit-config.yaml
!.template-type
!CHANGELOG.md
!LICENSE
!Makefile
!README.md
!release-please-config.json
!.release-please-manifest.json

# GitHub configuration
!/.github/
!/.github/CODEOWNERS
!/.github/PULL_REQUEST_TEMPLATE.md
!/.github/renovate.json5
!/.github/workflows/
!/.github/workflows/pr-validation.yaml
!/.github/workflows/security.yaml
!/.github/workflows/template-sync.yaml
!/.github/workflows/codeql.yaml
!/.github/workflows/scorecard.yaml
!/.github/workflows/release-please.yaml
!/.github/workflows/auto-merge.yaml
!/.github/workflows/terraform-deploy.yaml

# Runner data — overlaid onto the framework at deploy time
!/repos/
!/repos/public/
!/repos/public/**
!/repos/private/
!/repos/private/**

# Test fixtures — public-safe data used in pr-validation
!/tests/
!/tests/fixtures/
!/tests/fixtures/**

# Documentation (Diátaxis)
!/docs/
!/docs/README.md
!/docs/explanation/
!/docs/explanation/architecture.md
!/docs/explanation/testing-strategy.md
!/docs/explanation/threat-model.md
!/docs/reference/
!/docs/reference/invariants.md
!/docs/reference/release-gates.md
!/docs/how-to/
!/docs/how-to/develop-this-module.md
!/docs/decision-records/
!/docs/decision-records/README.md

# Tools
!/tools/
!/tools/check_docs_layout.py

# Policies
!/policies/
!/policies/opa/
!/policies/opa/.gitkeep
'''


UNIVERSAL_SEEDS = {
    "docs/README.md": DOCS_README,
    "docs/explanation/architecture.md": ARCHITECTURE_MD,
    "docs/explanation/testing-strategy.md": TESTING_STRATEGY_MD,
    "docs/explanation/threat-model.md": THREAT_MODEL_MD,
    "docs/reference/release-gates.md": RELEASE_GATES_MD,
    "docs/reference/invariants.md": INVARIANTS_MD,
    "docs/how-to/develop-this-module.md": HOWTO_DEVELOP_MD,
    "docs/decision-records/README.md": DECISION_RECORDS_README,
    "policies/opa/.gitkeep": "",
    "CHANGELOG.md": CHANGELOG_MD,
    "release-please-config.json": RELEASE_PLEASE_CONFIG,
    ".release-please-manifest.json": RELEASE_PLEASE_MANIFEST,
    ".github/CODEOWNERS": CODEOWNERS,
    ".github/PULL_REQUEST_TEMPLATE.md": PR_TEMPLATE,
}

FRAMEWORK_SEEDS = {
    "terraform/versions.tf": VERSIONS_TF,
    "terraform/variables.tf": VARIABLES_TF,
    "terraform/locals.tf": LOCALS_TF,
    "terraform/resources.tf": RESOURCES_TF,
    "terraform/outputs.tf": OUTPUTS_TF,
    "terraform/tests/.gitkeep": "",
    "docs/reference/terraform.md": REFERENCE_TERRAFORM_MD,
    "examples/minimal/main.tf": EXAMPLE_MAIN_TF,
    "examples/minimal/README.md": EXAMPLE_README_MD,
}

RUNNER_SEEDS = {
    "repos/public/.gitkeep": "",
    "repos/private/.gitkeep": "",
    "tests/fixtures/repos/public/example.yml": RUNNER_FIXTURE_PUBLIC,
    "tests/fixtures/repos/private/example.yml": RUNNER_FIXTURE_PRIVATE,
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("\n\n", 1)[1] if "\n\n" in __doc__ else "",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Path to the consumer repository root (default: cwd).",
    )
    parser.add_argument(
        "--type",
        choices=VALID_TYPES,
        required=True,
        help="Repo shape to seed: framework (self-contained module) or runner (deployer).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be created without writing any files.",
    )
    args = parser.parse_args()

    repo = args.repo_root.resolve()
    # Hard guard: refuse to seed inside terraform-template itself.
    if (repo / "contract" / "golden-template-contract.yaml").is_file() and \
       (repo / "sync" / "synced-files.yaml").is_file() and \
       (repo / ".github" / "workflows" / "reusable-template-sync.yaml").is_file():
        sys.stderr.write(
            f"refusing to seed {repo}: this looks like terraform-template itself.\n"
            "Run this script from a *consumer* repository's root.\n"
        )
        return 2

    seeds = dict(UNIVERSAL_SEEDS)
    if args.type == "framework":
        seeds.update(FRAMEWORK_SEEDS)
        gitignore_content = GITIGNORE_FRAMEWORK
    else:  # runner
        seeds.update(RUNNER_SEEDS)
        gitignore_content = GITIGNORE_RUNNER
    seeds[".template-type"] = f"{args.type}\n"

    created: list[str] = []
    skipped: list[str] = []
    for rel, content in seeds.items():
        target = repo / rel
        if target.exists():
            skipped.append(rel)
            continue
        if args.dry_run:
            created.append(rel)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        created.append(rel)

    # .gitignore — only seed deny-all if no .gitignore exists.
    gi = repo / ".gitignore"
    if not gi.exists():
        if not args.dry_run:
            gi.write_text(gitignore_content, encoding="utf-8")
        created.append(".gitignore")
    else:
        skipped.append(".gitignore")

    label = "[dry-run] " if args.dry_run else ""
    print(f"{label}Seed result for {repo.name} (type={args.type}):")
    print(f"  Created: {len(created)}")
    for f in sorted(created):
        print(f"    + {f}")
    print(f"  Skipped (already present): {len(skipped)}")
    for f in sorted(skipped):
        print(f"    . {f}")

    if not created:
        print("Nothing to seed; repo already has all scaffold files.")
        return 0
    print()
    print("Next steps:")
    print("  1. Review the seeded files and customize stubs.")
    print("  2. Bump the terraform-template SHA pin in template-sync.yaml so the")
    print("     next sync run delivers .terraform-docs.yml, .tflint.hcl, Makefile, etc.")
    print("  3. Add the nine caller workflows (pr-validation, security, codeql,")
    print("     scorecard, release-please, release-evidence, auto-merge,")
    print("     template-sync, org-adr-sync) plus — for runners —")
    print("     terraform-deploy.yaml.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
