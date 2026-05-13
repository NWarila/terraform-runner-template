# Repository-specific ADRs

ADRs in this directory record decisions specific to
`NWarila/terraform-runner-template` only. Decisions that apply to every
consumer of this template live one level up at
[`../0001-...md`, etc.](../) (template tier). Decisions that apply to every
repo in the org live in [`../org/`](../org/) as byte-identical mirrors of
`NWarila/.github`.

This template currently has **no** repo-specific ADRs — every decision in
play is either template-tier or org-mirrored. The `.gitkeep` placeholder
keeps the directory tracked so consumers derived from this template
inherit a complete decision-records skeleton.

When adding a repo-tier ADR (rare, only for decisions that genuinely don't
generalize to other Terraform consumers):

1. Pick the next unused 4-digit number in the `repo/` namespace (zero-padded).
2. Title it `NNNN-short-kebab-title.md`.
3. Use the canonical ADR-0001 format from `../org/0001-use-architecture-decision-records.md`.
4. Update the Status table on merge.

The `repo/` namespace is independent of both the `org/` namespace and the
template namespace per
[org ADR-0001](https://github.com/NWarila/.github/blob/main/docs/decision-records/0001-use-architecture-decision-records.md).
