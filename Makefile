PYTHON ?= python3
FRAMEWORK_SOURCE ?= ../terraform-framework-template/terraform
INTEGRATION_CASE ?= basic

.PHONY: help setup ruff yamllint opa-test opa-policy opa-plan manifest-check contract-check contract-tests lint policy docs-check integration ci verify

help:
	@printf "Targets:\\n"
	@printf "  setup          Install local Python lint dependencies\\n"
	@printf "  lint           Run Python/workflow lint checks\\n"
	@printf "  policy         Run OPA tests and policy evaluation\\n"
	@printf "  docs-check     Check docs layout and ADR index\\n"
	@printf "  ci             Run the repo-local quality gate\\n"
	@printf "  integration    Compose this runner with a framework checkout\\n"
	@printf "  verify         Run ci plus integration\\n"

setup:
	$(PYTHON) -m pip install --upgrade pyyaml==6.0.3 ruff==0.13.0 yamllint==1.35.1

# This is a META-TEMPLATE for Terraform-runner repos. It does not
# contain a `terraform/` directory of its own — the runner pattern
# is data-only (per ADR-template/0001 and the runner contract). The
# Makefile here lints + validates the META-template's surface; CI
# (`.github/workflows/ci.yaml`) runs the same set, plus a few
# checks that depend on workflow-level credentials.
#
# Derivative runners produced from this template inherit its file
# tree via GitHub's "Use this template" feature; their own Makefile
# `ci` target invokes this template's
# `reusable-terraform-validation.yaml` against an assembled
# framework-overlay tree.

ruff:
	$(PYTHON) tools/verify.py ruff

yamllint:
	$(PYTHON) tools/verify.py yamllint

# OPA policy tests. Exercises every deny rule in
# policies/opa/repo_hygiene.rego against pass + fail fixtures.
opa-test:
	opa test policies/opa

# OPA policy enforcement. Evaluates the policy against this repo's
# actual workflows. Runner templates have no terraform/ tree, so the
# policy's Terraform pinning rules are skipped here by design.
opa-policy:
	$(PYTHON) tools/verify.py opa-policy

# OPA plan enforcement. Runner templates do not own terraform/ directly,
# so this target evaluates a normalized safe plan fixture against the
# shared plan-aware package. Consumer runners evaluate their real plan JSON.
opa-plan:
	$(PYTHON) tools/verify.py opa-plan

# Validates baseline-manifest.json against the drift-gate manifest
# schema without installing drift-gate during CI. Catches a malformed
# template manifest before consumers' template-tier drift-gate fails on it.
manifest-check:
	$(PYTHON) tools/verify.py manifest-check

# Validates the runner-template contract manifest and this repo's
# template-facing shape. The contract is the source of truth for what
# every runner repo must have; a malformed or self-inconsistent
# contract silently breaks every validator that consumes it.
contract-check:
	$(PYTHON) tools/verify.py contract-check

contract-tests:
	$(PYTHON) tools/verify.py contract-tests

lint:
	$(PYTHON) tools/verify.py lint

policy:
	$(MAKE) opa-test
	$(MAKE) opa-policy
	$(MAKE) opa-plan

docs-check:
	$(PYTHON) tools/verify.py docs-check

integration:
	$(PYTHON) tools/verify.py integration --case $(INTEGRATION_CASE) --framework-source "$(FRAMEWORK_SOURCE)"

ci:
	$(PYTHON) tools/verify.py ci

verify:
	$(PYTHON) tools/verify.py verify --case $(INTEGRATION_CASE) --framework-source "$(FRAMEWORK_SOURCE)"
