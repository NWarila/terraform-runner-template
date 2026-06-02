# ADR-repo/0001: Use Do-Nothing Framework Template as Integration Reference

| Field          | Value                                   |
| -------------- | --------------------------------------- |
| Status         | Accepted                                |
| Date           | 2026-06-02                              |
| Authors        | Nick Warila (@NWarila)                  |
| Decision-maker | Nick Warila (sole portfolio maintainer) |
| Consulted      | Template-tier ADRs 0001–0005; docs/explanation/architecture.md |
| Informed       | Future contributors and consumers deriving from this template. |
| Reversibility  | Low (changing the reference framework would require updating fixtures and CI wiring) |
| Review-by      | N/A (Accepted)                          |

## TL;DR

`terraform-runner-template`'s integration fixture assembles runner data against
`NWarila/terraform-framework-template` — a do-nothing reference framework — rather
than a real production framework. This keeps CI credential-free and self-contained
while still verifying the full runner-meets-framework overlay path end-to-end.

## Context and Problem Statement

A Terraform runner repo has no executable Terraform module of its own. Its
correctness depends on the interplay between its inventory files
(`terraform/public/`, `terraform/private/`) and the framework it deploys
(the Terraform module that owns `github_repository`, `rulesets`, and other
resources). Validating a runner in isolation — without a real framework — leaves
the most failure-prone surface (the overlay path and version matching) untested.

At the same time, referencing a real framework with real infrastructure
resources would require live credentials, external state, and environment setup
that is inappropriate for template-repo CI. The CI constraint is: every check
on a PR must run in a standard GitHub Actions runner with no extra secrets.

## Decision Drivers

1. **Credential-free CI.** The `pr-validation.yaml` runner does not have access
   to production AWS credentials or a real Terraform state backend. Integration
   must complete without them.
2. **End-to-end overlay validation.** The `fixtures/integration/basic/` fixture
   must cover the full `reusable-terraform-validation.yaml` path: checkout
   framework, overlay runner data, run framework quality gate.
3. **Template independence.** The reference framework must be stable and under
   the same portfolio governance; it cannot be a transient external module.
4. **Reproducibility.** Any contributor cloning this template must be able to
   run `python tools/verify.py integration` without additional account setup,
   provided they have the framework checked out beside this repo.

## Considered Options

1. **`NWarila/terraform-framework-template` (do-nothing reference framework).**
   A no-op framework template under the same portfolio governance. Validates the
   overlay path and runner wiring without requiring live infrastructure.
2. **A real production framework (e.g. `nwarila-platform/github-terraform-framework`).**
   Would test against actual Terraform resources but requires live credentials,
   real state, and external service access — incompatible with credential-free PR CI.
3. **A synthetic in-tree stub module.** Keep a minimal Terraform module inside
   this template repository itself. Avoids the cross-repo dependency but means
   the template carries both runner and framework surfaces, violating the
   architectural separation stated in template-tier ADR-0001.

## Decision Outcome

Chosen option: **Option 1, `NWarila/terraform-framework-template` as the
integration reference.**

- `fixtures/integration/basic/` targets `terraform-framework-template` by default.
- `python tools/verify.py integration` resolves the framework from
  `../terraform-framework-template/terraform` (override via `--framework-source`).
- The `pr-validation.yaml` caller workflow passes `framework_repo:
  NWarila/terraform-framework-template` and a pinned `framework_ref` SHA.
- Renovate keeps the pinned `framework_ref` SHA current.

## Pros and Cons of the Options

### Option 1: Do-nothing framework template (chosen)

- **Good, because** CI runs credential-free on any standard GitHub Actions runner.
- **Good, because** overlay logic and version matching are validated against a
  real framework checkout, not a stub.
- **Good, because** the reference framework is under the same portfolio governance
  and ADR discipline.
- **Bad, because** contributors must check out `terraform-framework-template` beside
  this repo to run integration locally; `git clone` of this repo alone is not
  sufficient.
- **Neutral, because** Renovate bumps are scoped to the framework SHA, not the
  full set of framework resources.

### Option 2: Real production framework

- **Good, because** tests run against actual resources.
- **Bad, because** requires live credentials and state — incompatible with
  credential-free PR CI.
- **Bad, because** test isolation is lost; failures may be caused by live
  infrastructure state rather than runner logic.

### Option 3: In-tree stub module

- **Good, because** no cross-repo dependency for local development.
- **Bad, because** conflates runner and framework concerns in one repository.
- **Bad, because** duplicates framework-template testing surface; the stub drifts
  from the real framework over time.

## Confirmation

1. `pr-validation.yaml` in this template MUST pass `framework_repo:
   NWarila/terraform-framework-template` and a pinned `framework_ref` SHA.
2. `python tools/verify.py integration` MUST succeed against a sibling checkout of
   `terraform-framework-template` with no additional environment setup.
3. A change to the integration reference framework requires a superseding
   repo-tier ADR before merging.

## Consequences

### Positive

- Every PR on this template validates the full runner overlay path end-to-end
  without external credentials.
- Contributors have a clear, documented local development path.
- The reference framework is governed by the same portfolio discipline as this
  template.

### Negative

- Local integration requires a sibling checkout of `terraform-framework-template`.
  Single-repo clone is sufficient only for unit-level checks (`make lint`,
  `python tools/verify.py ci`).
- If `terraform-framework-template` diverges significantly (breaking interface
  changes), this template's integration fixture breaks until the pin is updated.

### Neutral

- This decision does not affect consumer runners, which pin to their own chosen
  framework via `framework_repo` and `framework_ref` inputs.

## Assumptions

This decision rests on the following assumptions. If any becomes false, this ADR should be revisited:

1. `NWarila/terraform-framework-template` remains a stable, maintained do-nothing reference that tracks the same Terraform CLI version range used by runner consumers.
2. The overlay interface between runner data and the framework (`terraform/repos/public`, `terraform/repos/private`) does not change in a way that requires a different default reference for validation.
3. Contributors performing local integration testing have access to GitHub and can clone `terraform-framework-template` beside this repo without additional authentication beyond a standard GitHub token.

## Supersedes

None.

## Superseded by

None (current).

## Implementing PRs

- Initial scaffold introducing `fixtures/integration/basic/` and the
  `reusable-terraform-validation.yaml` runner mode.

## Related ADRs

- [ADR-template/0001](../template/0001-pin-terraform-and-provider-versions-exactly.md) —
  exact-pin policy that applies to `framework_ref` and tool-version inputs.
- [ADR-template/0005](../template/0005-enforce-thin-runner-deployer-shape.md) —
  thin-runner shape; the runner owns data and callers only, not an in-tree module.
- [ADR-org/0001](../org/0001-use-architecture-decision-records.md) — three-tier ADR
  scope; this ADR is repo-tier because the do-nothing reference is specific to this
  template repo's own CI, not a rule imposed on consumers.

## Compliance Notes

None.
