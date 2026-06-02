# Architecture Decision Records

This directory holds the Architecture Decision Records (ADRs) governing this Terraform runner template. Per [org ADR-0001](org/0001-use-architecture-decision-records.md), ADRs are organized into three scopes:

- `org/` - byte-identical mirrors of org-baseline ADRs from [`NWarila/.github`](https://github.com/NWarila/.github). These apply to every repo in the org regardless of stack.
- `template/` - Terraform-runner-template ADRs owned by this repository. Runner consumers may mirror these for local documentation, but template-tier ADRs are no longer part of the byte-identical runner drift gate.
- `repo/` - repository-specific ADRs for one runner repository only. This template repo itself does not have repo-tier ADRs.

`terraform-runner-template` is itself a type-template: it owns the canonical runner command surface, consumer overlay contract, reusable validation workflow, and runner-tier decisions that derivative Terraform runner repositories inherit.

## Template ADRs

| ADR | Status | Decision |
| --- | --- | --- |
| [ADR-template/0001](template/0001-pin-terraform-and-provider-versions-exactly.md) | Accepted | Pin the Terraform CLI and every provider to exact versions. |
| [ADR-template/0002](template/0002-mandate-s3-state-backend.md) | Accepted (partial enforcement) | Mandate S3 backend, native locking, OIDC-only auth, encryption, versioning, and access logging policy for runner consumers. |
| [ADR-template/0004](template/0004-isolate-pull-request-target-triggers.md) | Accepted | Keep `pull_request_target` isolated to trusted-bot auto-merge, never release publishing. |
| [ADR-template/0005](template/0005-enforce-thin-runner-deployer-shape.md) | Accepted | Enforce Terraform runner consumers as thin data-only deployers. |
| [ADR-0006](org/0006-keep-github-control-planes-namespace-local.md) | Accepted | Keep GitHub control planes namespace-local. |
| [ADR-0007](org/0007-centralize-universal-ci-reusables-within-each-namespace.md) | Accepted | Centralize universal CI reusables within each namespace. |
| [ADR-0008](org/0008-enforce-repo-hygiene-by-repo-type.md) | Accepted | Enforce repo hygiene by repo type. |
| [ADR-0009](org/0009-classify-baseline-manifest-byte-identity.md) | Accepted | Classify baseline-manifest byte identity. |
| [ADR-0010](org/0010-keep-ai-attribution-out-of-version-control.md) | Accepted | Keep AI attribution out of version control. |

ADR-template/0003 was withdrawn before release and is intentionally absent.

## Org ADRs

The `org/` scope is mirrored from `NWarila/.github` and enforced by the org drift gate.

| ADR | Status | Decision |
| --- | --- | --- |
| [ADR-0001](org/0001-use-architecture-decision-records.md) | Accepted | Use ADRs to document design rationale. |
| [ADR-0002](org/0002-adopt-diataxis-documentation-framework.md) | Accepted | Use Diátaxis for non-ADR documentation. |
| [ADR-0003](org/0003-use-deny-all-gitignore-strategy.md) | Accepted | Use deny-all `.gitignore` allowlists. |
| [ADR-0004](org/0004-use-renovate-for-dependency-updates.md) | Accepted | Use Renovate for dependency updates. |
| [ADR-0005](org/0005-pin-terraform-and-provider-versions-exactly.md) | Accepted | Pin Terraform and provider versions exactly. |

## Repo ADRs

ADRs specific to `NWarila/terraform-runner-template` as a repo (not rules imposed on consumers).

| ADR | Status | Decision |
| --- | --- | --- |
| [ADR-repo/0001](repo/0001-use-do-nothing-framework-as-integration-reference.md) | Accepted | Use `terraform-framework-template` as the credential-free integration reference for this template's own CI. |
