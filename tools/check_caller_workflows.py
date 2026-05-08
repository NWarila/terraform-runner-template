#!/usr/bin/env python3
"""Verify a consumer repository's caller workflows match the canonical shape.

Each caller workflow on a consumer is a thin wrapper that delegates to a
reusable workflow in NWarila/terraform-template (or, for `terraform-deploy`,
in the framework being consumed). This script checks structural conformance.

Universal callers (every consumer):
  - .github/workflows/template-sync.yaml
      uses: NWarila/terraform-template/.github/workflows/reusable-template-sync.yaml@<sha>
      with: template_ref: <same sha>
  - .github/workflows/pr-validation.yaml
      uses: ...reusable-terraform-validation.yaml@<sha>
      framework: with mode: full and the four tool versions
      runner:    with mode: runner, framework_repo, framework_ref, overlay_paths
  - .github/workflows/security.yaml
      uses: ...reusable-iac-security.yaml@<sha>
  - .github/workflows/codeql.yaml
      uses: ...reusable-codeql.yaml@<sha>
  - .github/workflows/scorecard.yaml
      uses: ...reusable-scorecard.yaml@<sha>
  - .github/workflows/release-please.yaml
      uses: ...reusable-release-please.yaml@<sha>
  - .github/workflows/auto-merge.yaml
      uses: ...reusable-auto-merge.yaml@<sha>

Runner-only caller:
  - .github/workflows/terraform-deploy.yaml
      uses: <framework>/.github/workflows/reusable-terraform-deploy.yaml@<sha>
      Validation here is loose: we only require an SHA pin and that some job
      uses a reusable workflow from a framework repo. The framework owns the
      shape of its own deploy reusable.

Repo type is detected the same way as check_template_contract.py.

Usage:
    check_caller_workflows.py [--repo-root PATH] [--type framework|runner]
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    sys.stderr.write(
        "error: PyYAML is required. Install with `pip install pyyaml`.\n"
    )
    sys.exit(2)


SHA_RE = re.compile(r"^[0-9a-f]{40}$")
TEMPLATE_PREFIX = "NWarila/terraform-template/.github/workflows/"
VALID_TYPES = ("framework", "runner")


@dataclass
class CallerSpec:
    file: str
    reusable: str
    required_inputs: list[str] = field(default_factory=list)
    sha_input_name: str | None = None
    required_values: dict[str, str] = field(default_factory=dict)
    must_not_be_false: list[str] = field(default_factory=list)
    must_not_be_true: list[str] = field(default_factory=list)


COMMON_TOOL_INPUTS = [
    "terraform_version",
    "tflint_version",
    "terraform_docs_version",
    "opa_version",
    "template_ref",
    "mode",
]


def callers_for(repo_type: str) -> list[CallerSpec]:
    common: list[CallerSpec] = [
        CallerSpec(
            file=".github/workflows/template-sync.yaml",
            reusable="reusable-template-sync.yaml",
            required_inputs=["template_ref"],
            sha_input_name="template_ref",
        ),
        CallerSpec(
            file=".github/workflows/security.yaml",
            reusable="reusable-iac-security.yaml",
            must_not_be_true=["zizmor_advisory", "trivy_advisory", "gitleaks_advisory"],
        ),
        CallerSpec(
            file=".github/workflows/codeql.yaml",
            reusable="reusable-codeql.yaml",
        ),
        CallerSpec(
            file=".github/workflows/scorecard.yaml",
            reusable="reusable-scorecard.yaml",
        ),
        CallerSpec(
            file=".github/workflows/release-please.yaml",
            reusable="reusable-release-please.yaml",
        ),
        CallerSpec(
            file=".github/workflows/release-evidence.yaml",
            reusable="reusable-release-evidence.yaml",
            required_inputs=["terraform_version"],
        ),
        CallerSpec(
            file=".github/workflows/auto-merge.yaml",
            reusable="reusable-auto-merge.yaml",
        ),
        CallerSpec(
            file=".github/workflows/org-adr-sync.yaml",
            reusable="reusable-org-adr-sync.yaml",
        ),
    ]
    if repo_type == "framework":
        common.append(
            CallerSpec(
                file=".github/workflows/pr-validation.yaml",
                reusable="reusable-terraform-validation.yaml",
                required_inputs=COMMON_TOOL_INPUTS,
                sha_input_name="template_ref",
                required_values={"mode": "full"},
                must_not_be_false=["run_contract_check"],
                must_not_be_true=["lint_advisory"],
            )
        )
    elif repo_type == "runner":
        common.append(
            CallerSpec(
                file=".github/workflows/pr-validation.yaml",
                reusable="reusable-terraform-validation.yaml",
                required_inputs=[
                    *COMMON_TOOL_INPUTS,
                    "framework_repo",
                    "framework_ref",
                    "overlay_paths",
                ],
                sha_input_name="template_ref",
                required_values={"mode": "runner"},
                must_not_be_false=["run_contract_check"],
                must_not_be_true=["lint_advisory"],
            )
        )
    return common


@dataclass
class Result:
    name: str
    passed: bool
    detail: str = ""


def find_reusable_job(workflow: dict, expected_reusable: str) -> tuple[dict, str] | None:
    for _name, job in (workflow.get("jobs") or {}).items():
        if not isinstance(job, dict):
            continue
        uses = job.get("uses")
        if not isinstance(uses, str):
            continue
        if uses.startswith(TEMPLATE_PREFIX) and uses.split("@", 1)[0].endswith(expected_reusable):
            return job, uses
    return None


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def value_text(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).strip()


def check_caller(repo_root: Path, spec: CallerSpec) -> list[Result]:
    target = repo_root / spec.file
    if not target.is_file():
        return [
            Result(
                name=f"caller:{spec.file}",
                passed=False,
                detail="caller workflow missing",
            )
        ]

    try:
        workflow = yaml.safe_load(target.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return [
            Result(
                name=f"caller:{spec.file}",
                passed=False,
                detail=f"YAML parse error: {exc}",
            )
        ]

    if not isinstance(workflow, dict):
        return [
            Result(
                name=f"caller:{spec.file}",
                passed=False,
                detail="workflow is not a mapping",
            )
        ]

    found = find_reusable_job(workflow, spec.reusable)
    if found is None:
        return [
            Result(
                name=f"caller:{spec.file}",
                passed=False,
                detail=f"no job calls {TEMPLATE_PREFIX}{spec.reusable}",
            )
        ]
    job, uses = found
    results: list[Result] = []

    _, version = uses.rsplit("@", 1)
    if not SHA_RE.match(version):
        results.append(
            Result(
                name=f"caller:{spec.file}:uses-sha",
                passed=False,
                detail=f"uses ref `@{version}` is not a 40-char SHA",
            )
        )
        version = None
    else:
        results.append(Result(name=f"caller:{spec.file}:uses-sha", passed=True))

    with_block = job.get("with") or {}
    if not isinstance(with_block, dict):
        with_block = {}
    for input_name in spec.required_inputs:
        if input_name not in with_block:
            results.append(
                Result(
                    name=f"caller:{spec.file}:input:{input_name}",
                    passed=False,
                    detail="missing required input",
                )
            )
        else:
            results.append(
                Result(name=f"caller:{spec.file}:input:{input_name}", passed=True)
            )

    for input_name, expected in spec.required_values.items():
        if input_name not in with_block:
            continue
        actual = value_text(with_block[input_name])
        results.append(
            Result(
                name=f"caller:{spec.file}:input-value:{input_name}",
                passed=actual == expected,
                detail="" if actual == expected else f"expected `{expected}`, got `{actual}`",
            )
        )

    for input_name in spec.must_not_be_false:
        if input_name not in with_block:
            results.append(
                Result(
                    name=f"caller:{spec.file}:input-policy:{input_name}",
                    passed=True,
                    detail="absent (default strict)",
                )
            )
            continue
        ok = truthy(with_block[input_name])
        results.append(
            Result(
                name=f"caller:{spec.file}:input-policy:{input_name}",
                passed=ok,
                detail="" if ok else "must not be false",
            )
        )

    for input_name in spec.must_not_be_true:
        if input_name not in with_block:
            results.append(
                Result(
                    name=f"caller:{spec.file}:input-policy:{input_name}",
                    passed=True,
                    detail="absent (default strict)",
                )
            )
            continue
        ok = not truthy(with_block[input_name])
        results.append(
            Result(
                name=f"caller:{spec.file}:input-policy:{input_name}",
                passed=ok,
                detail="" if ok else "must not be true",
            )
        )

    if spec.sha_input_name and version and spec.sha_input_name in with_block:
        ref_value = str(with_block[spec.sha_input_name]).strip()
        if ref_value != version:
            results.append(
                Result(
                    name=f"caller:{spec.file}:sha-coherence",
                    passed=False,
                    detail=(
                        f"`{spec.sha_input_name}` ({ref_value[:12]}...) "
                        f"differs from uses SHA ({version[:12]}...)"
                    ),
                )
            )
        else:
            results.append(
                Result(name=f"caller:{spec.file}:sha-coherence", passed=True)
            )

    return results


def check_runner_deploy(repo_root: Path) -> list[Result]:
    """Loose check that the runner's deploy caller pins an SHA on a reusable.

    The framework owns the shape of its own deploy reusable; we only enforce
    that the runner's caller is SHA-pinned and points at *some* reusable.
    """
    target = repo_root / ".github" / "workflows" / "terraform-deploy.yaml"
    if not target.is_file():
        return [
            Result(
                name="caller:.github/workflows/terraform-deploy.yaml",
                passed=False,
                detail="runner deploy caller workflow missing",
            )
        ]
    try:
        workflow = yaml.safe_load(target.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return [
            Result(
                name="caller:.github/workflows/terraform-deploy.yaml",
                passed=False,
                detail=f"YAML parse error: {exc}",
            )
        ]
    if not isinstance(workflow, dict):
        return [
            Result(
                name="caller:.github/workflows/terraform-deploy.yaml",
                passed=False,
                detail="workflow is not a mapping",
            )
        ]
    for _name, job in (workflow.get("jobs") or {}).items():
        if not isinstance(job, dict):
            continue
        uses = job.get("uses")
        if not isinstance(uses, str) or "@" not in uses:
            continue
        _, version = uses.rsplit("@", 1)
        if SHA_RE.match(version):
            return [
                Result(
                    name="caller:.github/workflows/terraform-deploy.yaml",
                    passed=True,
                )
            ]
    return [
        Result(
            name="caller:.github/workflows/terraform-deploy.yaml",
            passed=False,
            detail="no SHA-pinned reusable workflow call found",
        )
    ]


def detect_repo_type(repo_root: Path, cli_type: str | None) -> str | None:
    if cli_type:
        return cli_type if cli_type in VALID_TYPES else None
    type_file = repo_root / ".template-type"
    if type_file.is_file():
        declared = type_file.read_text(encoding="utf-8").strip()
        return declared if declared in VALID_TYPES else None
    if (repo_root / "terraform" / "versions.tf").is_file():
        return "framework"
    if (repo_root / "repos" / "public").is_dir() or (repo_root / "repos" / "private").is_dir():
        return "runner"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Root of the repository under inspection (default: cwd).",
    )
    parser.add_argument(
        "--type",
        choices=VALID_TYPES,
        default=None,
        help="Override repo type detection (default: infer from .template-type or layout).",
    )
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    repo_type = detect_repo_type(repo_root, args.type)
    if repo_type is None:
        sys.stderr.write(
            "error: cannot determine repo type. Pass --type framework|runner or "
            "create a .template-type file.\n"
        )
        return 2
    print(f"repo type: {repo_type}")
    print()

    all_results: list[Result] = []
    for spec in callers_for(repo_type):
        all_results.extend(check_caller(repo_root, spec))
    if repo_type == "runner":
        all_results.extend(check_runner_deploy(repo_root))

    failed = [r for r in all_results if not r.passed]
    for r in all_results:
        marker = "PASS" if r.passed else "FAIL"
        line = f"[{marker}] {r.name}"
        if r.detail:
            line += f" - {r.detail}"
        print(line)

    print()
    print(f"summary: {len(all_results) - len(failed)} passed, {len(failed)} failed")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
