# Architecture Decision Records

This directory holds the Architecture Decision Records (ADRs) governing this
Terraform-runner template and every repository derived from it.

ADRs are organized into three scopes per
[org ADR-0001](https://github.com/nwarila-platform/.github/blob/main/docs/decision-records/0001-use-architecture-decision-records.md):

- `docs/decision-records/` — **template-tier master copies.** Decisions that
  apply to every repository derived from this Terraform-runner template (but
  not necessarily to non-Terraform repos in the org). Mirrored byte-identical
  into every consumer's `docs/decision-records/template/` via drift-gate.
- `docs/decision-records/org/` — byte-identical mirrors of org-baseline ADRs
  from `nwarila-platform/.github`. Apply to every repo in the org regardless
  of stack.
- `docs/decision-records/repo/` — repository-specific ADRs. Reserved for
  decisions that apply only to a single consuming repo. This template repo
  itself does not have repo-tier ADRs (every decision here is either
  template-tier or org-mirrored).

## Template-tier index

| #                                                                  | Title                                          | Status   | Date       | Summary                                                                                          |
| ------------------------------------------------------------------ | ---------------------------------------------- | -------- | ---------- | ------------------------------------------------------------------------------------------------ |
| [template/0001](0001-pin-terraform-and-provider-versions-exactly.md) | Pin Terraform and Provider Versions Exactly | Accepted | 2026-05-05 | Every consumer of this template uses `=` exact-version constraints for Terraform and providers. |
| [template/0002](0002-mandate-s3-state-backend.md)                    | Mandate S3 as the State Backend | Accepted | 2026-05-09 | Every consumer uses `backend "s3"` with native `use_lockfile = true`, OIDC-only auth, encryption + versioning + access logging on the bucket. Replaces the implicit "consumer chooses" default. |

## Org-mirrored index

These are byte-identical copies of decisions made in
[`nwarila-platform/.github`](https://github.com/nwarila-platform/.github/tree/main/docs/decision-records).
The authoritative copies and Index live there; this section reflects what
this repo currently mirrors.

| #                                                            | Title                                                          | Status   | Date       |
| ------------------------------------------------------------ | -------------------------------------------------------------- | -------- | ---------- |
| [org/0001](org/0001-use-architecture-decision-records.md)    | Use Architecture Decision Records to Document Design Rationale | Accepted | 2026-04-22 |
| [org/0002](org/0002-adopt-diataxis-documentation-framework.md) | Adopt Diátaxis as the Documentation Framework                | Accepted | 2026-04-24 |
| [org/0003](org/0003-use-deny-all-gitignore-strategy.md)      | Use a Deny-All `.gitignore` Strategy                           | Accepted | 2026-04-25 |
| [org/0004](org/0004-use-renovate-for-dependency-updates.md)  | Use Renovate for Dependency Updates with Shared Org Baseline   | Accepted | 2026-05-05 |

## How drift is enforced

[`drift-gate`](https://github.com/NWarila/drift-gate) (a SHA-pinned composite
GitHub Action) runs on every PR. It byte-compares this repo's mirrored copies
against the canonical:

- For org-tier mirrors: the source of truth is `nwarila-platform/.github`.
  The check reads that repo's `baseline-manifest.json` and compares each
  listed file against the mirror in this repo. Configured in
  [`.github/workflows/drift-gate.yaml`](../../.github/workflows/drift-gate.yaml).
- For template-tier content: this repo IS the source of truth. The
  `baseline-manifest.json` at the root of this repo enumerates the
  template-tier ADRs that derivative consumers must mirror.

When a consumer is created from this template, it inherits the
`drift-gate.yaml` and the layout skeleton automatically. Each consumer adds a
**second** drift-gate invocation pinned to this template repo so the
template-tier ADRs are also enforced.
