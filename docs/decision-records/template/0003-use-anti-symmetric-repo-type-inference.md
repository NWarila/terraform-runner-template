# ADR-template/0003: Use Anti-Symmetric Repo-Type Inference

| Field          | Value                                   |
| -------------- | --------------------------------------- |
| Status         | Accepted                                |
| Date           | 2026-05-10                              |
| Authors        | Nick Warila (@NWarila)                  |
| Decision-maker | Nick Warila (sole portfolio maintainer) |
| Consulted      | Contract fixture behavior and ambiguity tests. |
| Informed       | Template consumers via repo-type detector fixtures. |
| Reversibility  | High                                    |
| Review-by      | N/A (Accepted)                          |

## TL;DR

The runner contract validator infers repository type only when exactly one
layout signal is present. If multiple signals are present, validation fails as
ambiguous unless the caller passes `--type`. The template repository validates
itself with `--type template`; downstream consumers should normally not need an
override.

## Context and Problem Statement

`tools/check_template_contract.py` validates three repository shapes:

- `template`: this runner template, including contract tooling and reusable
  workflows.
- `runner`: a data-only deployer with `repos/public/` or `repos/private/`.
- `framework`: a Terraform module with `terraform/versions.tf`.

The runner template intentionally contains template tooling and sample runner
data. A naive detector can therefore observe more than one layout signal.
Previously, template detection ran first, so an ambiguous layout could silently
fall through to `template`. That is the wrong failure mode for consumers: a real
runner that accidentally grows framework-shaped files should fail loudly rather
than be classified as a template.

## Decision Drivers

1. **Fail-closed validation.** Ambiguous repository shape should stop the run.
2. **Consumer clarity.** Real runners should not carry template-only sentinels.
3. **Self-validation support.** This template still needs to validate its own
   hybrid surface.
4. **Low ceremony.** Intentional hybrid layouts need one explicit flag, not a
   committed marker file that consumers may inherit.
5. **Reviewability.** The validator's type decision should be explainable from
   the repo layout and CLI arguments.

## Considered Options

1. Keep first-match inference, with template detection taking precedence.
2. Add a committed `.template-type` sentinel file.
3. Use anti-symmetric inference and require `--type` for intentional hybrids.
4. Remove inference and require every caller to pass `--type`.

## Decision Outcome

Chosen option: **Option 3, anti-symmetric inference with an explicit override.**

Repo-type detection works as follows:

- `--type` is the only override and is required for intentional hybrid layouts.
- Without `--type`, exactly one layout signal must be present.
- Multiple signals fail loudly as ambiguous.
- No `.template-type` sentinel is restored.

The template's own CI and Makefile pass `--type template` for self-validation.
Consumer runners rely on ordinary layout inference and fail if they accidentally
grow framework or template signals.

## Pros and Cons of the Options

### Option 1: Keep first-match inference

- **Good, because** it is simple and preserves older behavior.
- **Bad, because** ambiguity is hidden instead of surfaced.
- **Bad, because** validator ordering becomes a security-relevant detail.
- **Bad, because** a malformed consumer could pass as the wrong shape.

### Option 2: Add a `.template-type` sentinel

- **Good, because** template self-validation becomes unambiguous.
- **Neutral, because** the sentinel is easy to read.
- **Bad, because** consumers may inherit, preserve, or delete it incorrectly.
- **Bad, because** it adds another source of truth beside layout and the
  contract validator.

### Option 3: Anti-symmetric inference with `--type` override (chosen)

- **Good, because** accidental hybrid layouts fail loudly.
- **Good, because** ordinary consumers stay configuration-free.
- **Good, because** the template can still self-validate intentionally.
- **Bad, because** callers for intentional hybrids must remember the flag.

### Option 4: Require `--type` everywhere

- **Good, because** no inference is needed.
- **Bad, because** every downstream caller carries boilerplate.
- **Bad, because** a wrong explicit type can mask layout drift just as badly as
  first-match inference.

## Confirmation

Adherence to this ADR is confirmed by the following mechanisms. The wording
`MUST`, `SHOULD`, and `MAY` follows RFC 2119 conventions.

1. **Ambiguity check.** `tools/check_template_contract.py` MUST fail when more
   than one repo-type signal is present and `--type` is omitted.
2. **Template self-check.** This repository's CI MUST pass `--type template`
   when validating the template against its own contract.
3. **Fixture coverage.** `tools/run_repo_type_tests.py` MUST include passing
   and failing fixtures for no signal, single-signal, and multi-signal layouts.
4. **No sentinel check.** This template MUST NOT reintroduce a committed
   `.template-type` file as the primary type source of truth.
5. **Consumer contract path.** Runner consumers SHOULD rely on layout inference
   and only use `--type` for documented hybrid exceptions.

## Consequences

### Positive

- Accidental hybrid repositories fail during validation instead of passing as a
  template.
- Real runners remain data-only by default.
- Template self-validation stays explicit and reviewable.

### Negative

- Intentional hybrid repositories need an explicit validator flag and rationale.
- Developers reading a failed validation need to understand repo-type signals.

### Neutral

- The validator remains the source of truth for shape inference.
- The template repository is intentionally hybrid, but only when its CI says so.

## Assumptions

1. Repo layout remains a reliable signal for framework, runner, and template
   shape.
2. The template repository remains the only normal hybrid in this family.
3. Consumers that need hybrid behavior can document that exception in a
   repository-specific ADR.

## Supersedes

None.

## Superseded by

None (current).

## Implementing PRs

- [`afbd9a2`](https://github.com/NWarila/terraform-runner-template/commit/afbd9a2c5cae5549791cf4b3dda81a0470bcee5c) tightened runner validation inputs and contract behavior.
- [`7400021`](https://github.com/NWarila/terraform-runner-template/commit/7400021e15fad6a47c1afdaf904e4dcf0d5f6eb0) added the contract and policy gates that exercise repo-type inference through fixtures.

## Related ADRs

- [ADR-template/0001](0001-pin-terraform-and-provider-versions-exactly.md)
  establishes exact-pinning for Terraform consumers.
- [ADR-template/0002](0002-mandate-s3-state-backend.md) defines a runner
  backend expectation that applies only after the repo is correctly identified
  as runner-shaped.

## Compliance Notes

- NIST SP 800-53 Rev. 5 CM-2: explicit repo-shape validation supports a stable
  baseline configuration for runner consumers.
- NIST SP 800-218 SSDF PO.3: clear contract classification helps reviewers
  understand which security and validation rules apply to a repository.
