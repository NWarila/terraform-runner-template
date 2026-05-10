#!/usr/bin/env python3
"""Verify runner consumer workflows call the template reusables safely.

This is the workflow-level companion to ``check_template_contract.py``. The
contract manifest proves that required files exist; this script proves the
load-bearing caller workflows are wired to the right reusable workflows with
static, SHA-pinned inputs.

Usage:
    check_caller_workflows.py [--repo-root PATH]
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

try:
    import yaml
except ImportError:
    sys.stderr.write(
        "error: PyYAML is required. Install with `pip install pyyaml`.\n"
    )
    sys.exit(2)


SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
OWNER_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")

TEMPLATE_REPO = "NWarila/terraform-runner-template"
RUNNER_VALIDATION_WORKFLOW = ".github/workflows/reusable-terraform-validation.yaml"
FRAMEWORK_DEPLOY_WORKFLOW = ".github/workflows/reusable-terraform-deploy.yaml"

VALID_MODES = {"runner", "contract-and-lint"}
TOOL_VERSION_INPUTS = (
    "terraform_version",
    "tflint_version",
    "terraform_docs_version",
    "opa_version",
)
SAFE_OVERLAY_SOURCES = (
    "repos/public",
    "repos/private",
    "tests/fixtures",
)
SAFE_OVERLAY_DESTINATIONS = (
    "terraform/repos/public",
    "terraform/repos/private",
    "terraform/tests",
)


@dataclass(frozen=True)
class RuleResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass(frozen=True)
class ReusableWorkflowCall:
    repo: str
    workflow_path: str
    ref: str


@dataclass(frozen=True)
class PrValidationContext:
    mode: str
    template_ref: str
    framework_repo: str | None = None
    framework_ref: str | None = None


def parse_workflow(path: Path) -> tuple[dict[str, Any] | None, RuleResult | None]:
    if not path.is_file():
        return None, RuleResult(
            name=f"workflow:{path.as_posix()}",
            passed=False,
            detail="workflow file not found",
        )
    try:
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    except yaml.YAMLError as exc:
        return None, RuleResult(
            name=f"workflow:{path.as_posix()}",
            passed=False,
            detail=f"invalid YAML: {exc}",
        )
    if not isinstance(data, dict):
        return None, RuleResult(
            name=f"workflow:{path.as_posix()}",
            passed=False,
            detail="workflow root must be a mapping",
        )
    return data, RuleResult(name=f"workflow:{path.as_posix()}", passed=True)


def parse_reusable_uses(value: Any) -> ReusableWorkflowCall | None:
    if not isinstance(value, str) or "@" not in value:
        return None
    target, ref = value.rsplit("@", 1)
    marker = "/.github/workflows/"
    if marker not in target:
        return None
    repo, workflow_name = target.split(marker, 1)
    if not repo or not workflow_name:
        return None
    workflow_path = f".github/workflows/{workflow_name}"
    return ReusableWorkflowCall(repo=repo, workflow_path=workflow_path, ref=ref)


def reusable_jobs(
    workflow: dict[str, Any], workflow_path: str
) -> list[tuple[str, dict[str, Any], ReusableWorkflowCall]]:
    jobs = workflow.get("jobs")
    if not isinstance(jobs, dict):
        return []

    matches: list[tuple[str, dict[str, Any], ReusableWorkflowCall]] = []
    for job_id, job in jobs.items():
        if not isinstance(job_id, str) or not isinstance(job, dict):
            continue
        call = parse_reusable_uses(job.get("uses"))
        if call and call.workflow_path == workflow_path:
            matches.append((job_id, job, call))
    return matches


def require_string(
    mapping: dict[str, Any], key: str, *, result_name: str | None = None
) -> tuple[str | None, RuleResult]:
    name = result_name or f"input:{key}"
    if key not in mapping:
        return None, RuleResult(
            name=name,
            passed=False,
            detail="required input missing",
        )
    value = mapping[key]
    if not isinstance(value, str) or not value.strip():
        return None, RuleResult(
            name=name,
            passed=False,
            detail=f"must be a non-empty string, got {value!r}",
        )
    return value.strip(), RuleResult(name=name, passed=True)


def check_static_bool_input(
    inputs: dict[str, Any],
    key: str,
    *,
    safe_default: bool,
    required_value: bool,
) -> RuleResult:
    if key not in inputs:
        return RuleResult(
            name=f"input:{key}",
            passed=True,
            detail=f"default {str(safe_default).lower()}",
        )
    value = inputs[key]
    if value is required_value:
        return RuleResult(name=f"input:{key}", passed=True)
    if isinstance(value, str) and value.lower() == str(required_value).lower():
        return RuleResult(name=f"input:{key}", passed=True)
    return RuleResult(
        name=f"input:{key}",
        passed=False,
        detail=f"must be statically {str(required_value).lower()}, got {value!r}",
    )


def validate_semver_input(inputs: dict[str, Any], key: str) -> RuleResult:
    value, result = require_string(inputs, key)
    if value is None:
        return result
    if not SEMVER_RE.match(value):
        return RuleResult(
            name=f"input:{key}",
            passed=False,
            detail=f"must be exact X.Y.Z, got {value!r}",
        )
    return RuleResult(name=f"input:{key}", passed=True)


def normalize_posix_path(value: str) -> tuple[str | None, str]:
    candidate = value.strip().replace("\\", "/")
    if not candidate:
        return None, "path is empty"
    if candidate.startswith("/") or candidate.startswith("~"):
        return None, "path must be relative"
    if ":" in candidate:
        return None, "path must not contain a drive or URI separator"
    if any(char in candidate for char in "*?[]"):
        return None, "path must not contain globs"

    trimmed = candidate.rstrip("/")
    if not trimmed:
        return None, "path must not resolve to repository root"
    path = PurePosixPath(trimmed)
    if any(part in ("", ".", "..") for part in path.parts):
        return None, "path must not contain empty, dot, or dot-dot segments"
    return path.as_posix(), ""


def path_is_under(path: str, roots: tuple[str, ...]) -> bool:
    parts = PurePosixPath(path).parts
    for root in roots:
        root_parts = PurePosixPath(root).parts
        if parts == root_parts or parts[: len(root_parts)] == root_parts:
            return True
    return False


def local_path_from_posix(repo_root: Path, path: str) -> Path:
    return repo_root.joinpath(*PurePosixPath(path).parts)


def validate_overlay_paths(repo_root: Path, value: Any, *, input_name: str) -> RuleResult:
    if not isinstance(value, str) or not value.strip():
        return RuleResult(
            name=f"input:{input_name}",
            passed=False,
            detail="must contain at least one overlay entry",
        )

    problems: list[str] = []
    entries = 0
    for lineno, raw_line in enumerate(value.splitlines(), 1):
        entry = raw_line.split("#", 1)[0].strip()
        if not entry:
            continue
        entries += 1
        if entry.count("=>") != 1:
            problems.append(f"line {lineno}: expected exactly one `=>` separator")
            continue

        source_raw, destination_raw = (part.strip() for part in entry.split("=>", 1))
        source, source_error = normalize_posix_path(source_raw)
        destination, destination_error = normalize_posix_path(destination_raw)
        if source is None:
            problems.append(f"line {lineno}: source {source_error}")
            continue
        if destination is None:
            problems.append(f"line {lineno}: destination {destination_error}")
            continue
        if not path_is_under(source, SAFE_OVERLAY_SOURCES):
            problems.append(
                f"line {lineno}: source {source!r} is outside allowed runner data paths"
            )
        elif not local_path_from_posix(repo_root, source).exists():
            problems.append(f"line {lineno}: source {source!r} does not exist")
        if not path_is_under(destination, SAFE_OVERLAY_DESTINATIONS):
            problems.append(
                f"line {lineno}: destination {destination!r} is outside terraform data paths"
            )

    if entries == 0:
        problems.append("no non-comment overlay entries found")

    return RuleResult(
        name=f"input:{input_name}",
        passed=not problems,
        detail=f"{entries} entries" if not problems else "; ".join(problems),
    )


def check_pr_validation(
    repo_root: Path,
) -> tuple[list[RuleResult], PrValidationContext | None]:
    path = repo_root / ".github" / "workflows" / "pr-validation.yaml"
    workflow, parse_result = parse_workflow(path)
    results = [parse_result] if parse_result else []
    if workflow is None:
        return results, None

    matches = reusable_jobs(workflow, RUNNER_VALIDATION_WORKFLOW)
    if not matches:
        results.append(
            RuleResult(
                name="pr-validation:runner-reusable",
                passed=False,
                detail=f"no job calls {TEMPLATE_REPO}/{RUNNER_VALIDATION_WORKFLOW}",
            )
        )
        return results, None
    if len(matches) != 1:
        results.append(
            RuleResult(
                name="pr-validation:runner-reusable",
                passed=False,
                detail=f"expected exactly one caller job, found {len(matches)}",
            )
        )
        return results, None

    job_id, job, call = matches[0]
    results.append(
        RuleResult(
            name="pr-validation:runner-reusable",
            passed=True,
            detail=f"job {job_id}",
        )
    )

    repo_ok = call.repo.lower() == TEMPLATE_REPO.lower()
    results.append(
        RuleResult(
            name="pr-validation:runner-template-repo",
            passed=repo_ok,
            detail="" if repo_ok else f"got {call.repo!r}, expected {TEMPLATE_REPO!r}",
        )
    )

    ref_ok = SHA_RE.match(call.ref) is not None
    results.append(
        RuleResult(
            name="pr-validation:runner-template-ref",
            passed=ref_ok,
            detail="" if ref_ok else f"reusable ref must be a 40-char SHA, got {call.ref!r}",
        )
    )

    inputs = job.get("with")
    if not isinstance(inputs, dict):
        results.append(
            RuleResult(
                name="pr-validation:with",
                passed=False,
                detail="caller job must define a `with` mapping",
            )
        )
        return results, None
    results.append(RuleResult(name="pr-validation:with", passed=True))

    for key in TOOL_VERSION_INPUTS:
        results.append(validate_semver_input(inputs, key))

    template_ref, template_ref_result = require_string(inputs, "template_ref")
    results.append(template_ref_result)
    if template_ref is not None:
        template_ref_ok = SHA_RE.match(template_ref) is not None
        results.append(
            RuleResult(
                name="input:template_ref_sha",
                passed=template_ref_ok,
                detail=""
                if template_ref_ok
                else f"template_ref must be a 40-char SHA, got {template_ref!r}",
            )
        )
        template_ref_matches = template_ref == call.ref
        results.append(
            RuleResult(
                name="input:template_ref_matches_reusable",
                passed=template_ref_matches,
                detail=""
                if template_ref_matches
                else f"template_ref {template_ref!r} does not match reusable @{call.ref}",
            )
        )

    mode, mode_result = require_string(inputs, "mode", result_name="input:mode_present")
    results.append(mode_result)
    if mode is not None:
        mode_ok = mode in VALID_MODES
        results.append(
            RuleResult(
                name="input:mode",
                passed=mode_ok,
                detail="" if mode_ok else f"expected one of {sorted(VALID_MODES)}, got {mode!r}",
            )
        )

    results.append(
        check_static_bool_input(
            inputs,
            "run_contract_check",
            safe_default=True,
            required_value=True,
        )
    )
    results.append(
        check_static_bool_input(
            inputs,
            "lint_advisory",
            safe_default=False,
            required_value=False,
        )
    )

    if mode != "runner":
        if mode in VALID_MODES and template_ref is not None:
            return results, PrValidationContext(mode=mode, template_ref=template_ref)
        return results, None

    framework_repo, framework_repo_result = require_string(
        inputs, "framework_repo", result_name="input:framework_repo_present"
    )
    results.append(framework_repo_result)
    if framework_repo is not None:
        framework_repo_ok = OWNER_REPO_RE.match(framework_repo) is not None
        results.append(
            RuleResult(
                name="input:framework_repo",
                passed=framework_repo_ok,
                detail=""
                if framework_repo_ok
                else f"framework_repo must be a static owner/repo, got {framework_repo!r}",
            )
        )

    framework_ref, framework_ref_result = require_string(
        inputs, "framework_ref", result_name="input:framework_ref_present"
    )
    results.append(framework_ref_result)
    if framework_ref is not None:
        framework_ref_ok = SHA_RE.match(framework_ref) is not None
        results.append(
            RuleResult(
                name="input:framework_ref",
                passed=framework_ref_ok,
                detail=""
                if framework_ref_ok
                else f"framework_ref must be a 40-char SHA, got {framework_ref!r}",
            )
        )

    results.append(validate_overlay_paths(repo_root, inputs.get("overlay_paths"), input_name="overlay_paths"))

    if template_ref is None or framework_repo is None or framework_ref is None:
        return results, None
    return results, PrValidationContext(
        mode=mode,
        template_ref=template_ref,
        framework_repo=framework_repo,
        framework_ref=framework_ref,
    )


def check_terraform_deploy(repo_root: Path, pr: PrValidationContext) -> list[RuleResult]:
    path = repo_root / ".github" / "workflows" / "terraform-deploy.yaml"
    workflow, parse_result = parse_workflow(path)
    results = [parse_result] if parse_result else []
    if workflow is None:
        return results

    matches = reusable_jobs(workflow, FRAMEWORK_DEPLOY_WORKFLOW)
    if not matches:
        results.append(
            RuleResult(
                name="terraform-deploy:framework-reusable",
                passed=False,
                detail="no job calls a framework reusable-terraform-deploy workflow",
            )
        )
        return results
    if len(matches) != 1:
        results.append(
            RuleResult(
                name="terraform-deploy:framework-reusable",
                passed=False,
                detail=f"expected exactly one deploy caller job, found {len(matches)}",
            )
        )
        return results

    job_id, job, call = matches[0]
    results.append(
        RuleResult(
            name="terraform-deploy:framework-reusable",
            passed=True,
            detail=f"job {job_id}",
        )
    )

    repo_ok = pr.framework_repo is not None and call.repo.lower() == pr.framework_repo.lower()
    results.append(
        RuleResult(
            name="terraform-deploy:framework-repo_matches_pr_validation",
            passed=repo_ok,
            detail=""
            if repo_ok
            else f"deploy uses {call.repo!r}, pr-validation uses {pr.framework_repo!r}",
        )
    )

    ref_ok = SHA_RE.match(call.ref) is not None
    results.append(
        RuleResult(
            name="terraform-deploy:framework-ref_sha",
            passed=ref_ok,
            detail="" if ref_ok else f"deploy reusable ref must be a 40-char SHA, got {call.ref!r}",
        )
    )

    pr_ref_ok = pr.framework_ref is not None and call.ref == pr.framework_ref
    results.append(
        RuleResult(
            name="terraform-deploy:framework-ref_matches_pr_validation",
            passed=pr_ref_ok,
            detail=""
            if pr_ref_ok
            else f"deploy @{call.ref} does not match pr-validation framework_ref {pr.framework_ref!r}",
        )
    )

    inputs = job.get("with")
    if not isinstance(inputs, dict):
        results.append(
            RuleResult(
                name="terraform-deploy:with",
                passed=False,
                detail="deploy caller job must define a `with` mapping",
            )
        )
        return results
    results.append(RuleResult(name="terraform-deploy:with", passed=True))

    deploy_framework_ref, deploy_framework_ref_result = require_string(
        inputs,
        "framework_ref",
        result_name="terraform-deploy:input:framework_ref_present",
    )
    results.append(deploy_framework_ref_result)
    if deploy_framework_ref is not None:
        sha_ok = SHA_RE.match(deploy_framework_ref) is not None
        results.append(
            RuleResult(
                name="terraform-deploy:input:framework_ref_sha",
                passed=sha_ok,
                detail=""
                if sha_ok
                else f"framework_ref must be a 40-char SHA, got {deploy_framework_ref!r}",
            )
        )
        matches_uses = deploy_framework_ref == call.ref
        results.append(
            RuleResult(
                name="terraform-deploy:input:framework_ref_matches_reusable",
                passed=matches_uses,
                detail=""
                if matches_uses
                else f"framework_ref {deploy_framework_ref!r} does not match reusable @{call.ref}",
            )
        )

    if "overlay_paths" in inputs and inputs["overlay_paths"]:
        results.append(
            validate_overlay_paths(
                repo_root,
                inputs["overlay_paths"],
                input_name="terraform-deploy.overlay_paths",
            )
        )

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Root of the runner repository under inspection (default: cwd).",
    )
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    results, pr_context = check_pr_validation(repo_root)
    if pr_context and pr_context.mode == "runner":
        results.extend(check_terraform_deploy(repo_root, pr_context))

    failed = [result for result in results if not result.passed]
    for result in results:
        marker = "PASS" if result.passed else "FAIL"
        line = f"[{marker}] {result.name}"
        if result.detail:
            line += f" - {result.detail}"
        print(line)

    print()
    print(f"summary: {len(results) - len(failed)} passed, {len(failed)} failed")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
