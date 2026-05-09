PYTHON ?= python3

# This is a META-TEMPLATE for Terraform-runner repos. It does not
# contain a `terraform/` directory of its own — the runner pattern
# is data-only (per ADR-template/0001 and the runner contract). The
# Makefile here lints + validates the META-template's surface; CI
# (`.github/workflows/self-ci.yaml`) runs the same set, plus a few
# checks that depend on workflow-level credentials.
#
# Derivative runners produced from this template inherit its file
# tree via GitHub's "Use this template" feature; their own Makefile
# `ci` target invokes this template's
# `reusable-terraform-validation.yaml` against an assembled
# framework-overlay tree.

ruff:
	$(PYTHON) -m pip install --no-cache-dir ruff==0.13.0
	ruff check tools/

yamllint:
	$(PYTHON) -m pip install --no-cache-dir yamllint==1.35.1
	yamllint -d "{ extends: relaxed, rules: { line-length: disable, document-start: disable, comments: disable, truthy: {check-keys: false} } }" .github/workflows/ contract/

# Validates baseline-manifest.json against drift-gate's stdlib
# schema. Same loader the org canonical's self-ci uses, installed
# from the SHA-pinned drift-gate ref. Catches a malformed template
# manifest BEFORE consumers' template-tier drift-gate fails on it.
manifest-check:
	$(PYTHON) -m pip install --no-cache-dir 'git+https://github.com/NWarila/drift-gate@d835ae411f1e55e25b2b6c079d5891e7345a043c'
	$(PYTHON) -c "from pathlib import Path; from baseline.manifest import load_manifest; m = load_manifest(Path('baseline-manifest.json')); print(f'manifest: version={m.version}, files={len(m.files)}'); missing = [f.source for f in m.files if not Path(f.source).is_file()]; assert not missing, f'sources missing: {missing}'; print('all sources resolve on disk')"

# Validates the runner-template contract YAML is well-formed. The
# contract is the source of truth for what every runner repo must
# have; a malformed contract silently breaks every validator that
# consumes it.
contract-check:
	$(PYTHON) -m pip install --no-cache-dir pyyaml==6.0.3
	$(PYTHON) -c "import yaml; spec = yaml.safe_load(open('contract/runner-template-contract.yaml')); assert spec['version'] == '2', f'unexpected contract version: {spec.get(\"version\")}'; assert 'universal' in spec; assert 'runner' in spec['types']; assert 'workflow_pinning' in spec; print('runner-template contract looks well-formed')"

ci:
	$(MAKE) ruff
	$(MAKE) yamllint
	$(MAKE) manifest-check
	$(MAKE) contract-check
