#!/usr/bin/env python3
"""Run validator contract fixtures against generated consumer workflows."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


# Each marker is a tuple of substrings that must all appear in the same
# `[FAIL]` line emitted by the validator. Single-element tuples match a
# single substring; multi-element tuples let a fixture pin specific parts
# of a fail line without coupling to the full message format.
Marker = tuple[str, ...]

EXPECTED_BAD_FAILURES: dict[str, tuple[Marker, ...]] = {
    "bad-template-ref-tag": (
        (".github/workflows/pr-validation.yaml",),
    ),
}

EXPECTED_BAD_CONTRACT_FAILURES: dict[str, tuple[Marker, ...]] = {
    "bad-drift-template-only": (
        (
            "content:.github/workflows/drift-gate.yaml",
            "NWarila/\\.github",
            "required pattern not found",
        ),
    ),
    "bad-deploy-missing-framework-reusable": (
        ("content:.github/workflows/terraform-deploy.yaml", "required pattern not found"),
    ),
    "bad-pr-validation-manual-only": (
        (
            "content:.github/workflows/pr-validation.yaml",
            "required pattern not found",
        ),
    ),
    "bad-renovate-org-baseline": (
        (
            "content:.github/renovate.json5",
            "github>NWarila/terraform-runner-template",
            "required pattern not found",
        ),
        (
            "content:.github/renovate.json5",
            "github>NWarila/\\.github",
            "forbidden pattern present",
        ),
    ),
    "bad-local-reusable-workflow": (
        ("forbidden:.github/workflows/reusable-*.yaml", "reusable-codeql.yaml"),
    ),
    "bad-local-reusable-workflow-yml": (
        ("forbidden:.github/workflows/reusable-*.yml", "reusable-codeql.yml"),
    ),
    "bad-release-local-reusables": (
        (
            "content:.github/workflows/release.yaml",
            "reusable-release-please",
            "required pattern not found",
        ),
        (
            "content:.github/workflows/release.yaml",
            "reusable-release-(please|evidence)",
            "forbidden pattern present",
        ),
    ),
    "bad-security-local-reusables": (
        (
            "content:.github/workflows/security.yaml",
            "reusable-iac-security",
            "required pattern not found",
        ),
        (
            "content:.github/workflows/security.yaml",
            "reusable-(iac-security|codeql|scorecard)",
            "forbidden pattern present",
        ),
    ),
}


@dataclass(frozen=True)
class Fixture:
    name: str
    path: Path
    should_pass: bool
    expected_failures: tuple[Marker, ...] = ()


@dataclass(frozen=True)
class FixtureRun:
    fixture: Fixture
    returncode: int
    stdout: str
    stderr: str
    passed: bool
    detail: str


def discover_fixtures(
    fixtures_root: Path, expected_failures: dict[str, tuple[Marker, ...]]
) -> tuple[list[Fixture], list[str]]:
    if not fixtures_root.is_dir():
        return [], [f"fixtures root not found: {fixtures_root}"]

    fixture_dirs = sorted(path for path in fixtures_root.iterdir() if path.is_dir())
    names = {path.name for path in fixture_dirs}
    errors: list[str] = []

    if "good" not in names:
        errors.append("missing required passing fixture: good")
    if not any(name.startswith("bad-") for name in names):
        errors.append("expected at least one bad-* fixture")

    unknown = sorted(
        name for name in names if name != "good" and not name.startswith("bad-")
    )
    for name in unknown:
        errors.append(f"unexpected consumer fixture name: {name}")

    fixtures: list[Fixture] = []
    good = fixtures_root / "good"
    if good.is_dir():
        fixtures.append(Fixture(name="good", path=good, should_pass=True))

    for path in fixture_dirs:
        if not path.name.startswith("bad-"):
            continue
        fixtures.append(
            Fixture(
                name=path.name,
                path=path,
                should_pass=False,
                expected_failures=expected_failures.get(path.name, ()),
            )
        )

    return fixtures, errors


def missing_expected_failures(
    stdout: str, expected_failures: tuple[Marker, ...]
) -> list[str]:
    fail_lines = [line for line in stdout.splitlines() if line.startswith("[FAIL] ")]
    missing: list[str] = []
    for fragments in expected_failures:
        if not any(all(fragment in line for fragment in fragments) for line in fail_lines):
            missing.append(" + ".join(fragments))
    return missing


def run_fixture(repo_root: Path, validator: Path, fixture: Fixture) -> FixtureRun:
    completed = subprocess.run(
        [
            sys.executable,
            str(validator),
            "--repo-root",
            str(fixture.path),
        ],
        cwd=repo_root,
        capture_output=True,
        check=False,
        text=True,
    )

    if fixture.should_pass:
        passed = completed.returncode == 0
        detail = "expected success"
        if not passed:
            detail = f"expected success, got exit {completed.returncode}"
    else:
        missing = missing_expected_failures(completed.stdout, fixture.expected_failures)
        passed = completed.returncode != 0 and not missing
        detail = "expected failure"
        if completed.returncode == 0:
            detail = "expected failure, got exit 0"
        elif missing:
            detail = "missing expected marker(s): " + ", ".join(missing)

    return FixtureRun(
        fixture=fixture,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        passed=passed,
        detail=detail,
    )


def prepare_contract_repo(repo_root: Path, fixture: Fixture, temp_root: Path) -> Path:
    """Build a full runner-shaped repo by overlaying a small fixture."""
    target = temp_root / fixture.name
    shutil.copytree(
        repo_root,
        target,
        ignore=shutil.ignore_patterns(
            ".git",
            ".mypy_cache",
            ".pytest_cache",
            ".ruff_cache",
            ".terraform",
            ".venv",
            "__pycache__",
        ),
    )
    prune_template_only_runner_paths(target)
    shutil.copytree(fixture.path, target, dirs_exist_ok=True)
    return target


def prune_template_only_runner_paths(target: Path) -> None:
    """Remove template-owned ballast before runner contract fixture overlays."""
    for rel in ("tools", "policies"):
        path = target / rel
        if path.exists():
            shutil.rmtree(path)

    makefile = target / "Makefile"
    if makefile.exists():
        makefile.unlink()

    workflows = target / ".github" / "workflows"
    if not workflows.is_dir():
        return
    for path in workflows.glob("reusable-*.y*ml"):
        if path.name == "reusable-auto-merge.yaml":
            continue
        path.unlink()


def run_contract_fixture(
    repo_root: Path, validator: Path, contract: Path, fixture: Fixture
) -> FixtureRun:
    with tempfile.TemporaryDirectory(prefix="runner-contract-") as temp:
        fixture_repo = prepare_contract_repo(repo_root, fixture, Path(temp))
        completed = subprocess.run(
            [
                sys.executable,
                str(validator),
                "--repo-root",
                str(fixture_repo),
                "--contract",
                str(contract),
                "--template-root",
                str(repo_root),
                "--type",
                "runner",
            ],
            cwd=repo_root,
            capture_output=True,
            check=False,
            text=True,
        )

    if fixture.should_pass:
        passed = completed.returncode == 0
        detail = "expected success"
        if not passed:
            detail = f"expected success, got exit {completed.returncode}"
    else:
        missing = missing_expected_failures(completed.stdout, fixture.expected_failures)
        passed = completed.returncode != 0 and not missing
        detail = "expected failure"
        if completed.returncode == 0:
            detail = "expected failure, got exit 0"
        elif missing:
            detail = "missing expected marker(s): " + ", ".join(missing)

    return FixtureRun(
        fixture=fixture,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        passed=passed,
        detail=detail,
    )


def print_stream(label: str, text: str) -> None:
    if not text.strip():
        return
    print(f"--- {label} ---")
    print(text.rstrip())


def run_fixtures(fixtures: list[Fixture], validator: Path, repo_root: Path) -> int:
    runs = [run_fixture(repo_root, validator, fixture) for fixture in fixtures]
    failures = [run for run in runs if not run.passed]

    for run in runs:
        marker = "PASS" if run.passed else "FAIL"
        print(
            f"[{marker}] {run.fixture.name}: {run.detail} "
            f"(exit {run.returncode})"
        )
        if not run.passed:
            print_stream(f"{run.fixture.name} stdout", run.stdout)
            print_stream(f"{run.fixture.name} stderr", run.stderr)

    print()
    print(f"summary: {len(runs) - len(failures)} passed, {len(failures)} failed")
    return 0 if not failures else 1


def run_contract_fixtures(
    fixtures: list[Fixture], validator: Path, contract: Path, repo_root: Path
) -> int:
    runs = [
        run_contract_fixture(repo_root, validator, contract, fixture)
        for fixture in fixtures
    ]
    failures = [run for run in runs if not run.passed]

    for run in runs:
        marker = "PASS" if run.passed else "FAIL"
        print(
            f"[{marker}] contract/{run.fixture.name}: {run.detail} "
            f"(exit {run.returncode})"
        )
        if not run.passed:
            print_stream(f"contract/{run.fixture.name} stdout", run.stdout)
            print_stream(f"contract/{run.fixture.name} stderr", run.stderr)

    print()
    print(
        "contract summary: "
        f"{len(runs) - len(failures)} passed, {len(failures)} failed"
    )
    return 0 if not failures else 1


def run_malformed_contract_check(
    fixtures: list[Fixture], validator: Path, contract: Path, repo_root: Path
) -> int:
    good = next((fixture for fixture in fixtures if fixture.name == "good"), None)
    if good is None:
        print("[FAIL] contract/malformed-forbidden-path: missing good fixture")
        return 1

    text = contract.read_text(encoding="utf-8")
    malformed = text.replace(
        "    - path: tools/\n",
        "    - name: malformed-forbidden-entry\n    - path: tools/\n",
        1,
    )
    if malformed == text:
        print("[FAIL] contract/malformed-forbidden-path: insertion point not found")
        return 1

    with tempfile.TemporaryDirectory(prefix="runner-contract-malformed-") as temp:
        temp_root = Path(temp)
        malformed_contract = temp_root / "runner-template-contract.yaml"
        malformed_contract.write_text(malformed, encoding="utf-8")
        fixture_repo = prepare_contract_repo(repo_root, good, temp_root)
        completed = subprocess.run(
            [
                sys.executable,
                str(validator),
                "--repo-root",
                str(fixture_repo),
                "--contract",
                str(malformed_contract),
                "--template-root",
                str(repo_root),
                "--type",
                "runner",
            ],
            cwd=repo_root,
            capture_output=True,
            check=False,
            text=True,
        )

    expected_marker = "forbidden:<malformed-entry>"
    passed = completed.returncode != 0 and expected_marker in completed.stdout
    marker = "PASS" if passed else "FAIL"
    detail = "expected malformed forbidden_paths failure"
    if not passed:
        detail = f"missing expected marker: {expected_marker}"
    print(f"[{marker}] contract/malformed-forbidden-path: {detail}")
    if not passed:
        print_stream("contract/malformed-forbidden-path stdout", completed.stdout)
        print_stream("contract/malformed-forbidden-path stderr", completed.stderr)
    print()
    return 0 if passed else 1


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    default_caller_validator = repo_root / "tools" / "check_caller_workflows.py"
    default_contract_validator = repo_root / "tools" / "check_template_contract.py"
    default_contract = repo_root / "contract" / "runner-template-contract.yaml"

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixtures-root",
        type=Path,
        default=repo_root / "tests" / "fixtures" / "consumers",
        help="Directory containing good and bad-* consumer fixtures.",
    )
    parser.add_argument(
        "--validator",
        type=Path,
        default=default_caller_validator,
        help="Path to check_caller_workflows.py.",
    )
    parser.add_argument(
        "--contract-fixtures-root",
        type=Path,
        default=repo_root / "tests" / "fixtures" / "contract",
        help="Directory containing good and bad-* check_template_contract fixtures.",
    )
    parser.add_argument(
        "--contract-validator",
        type=Path,
        default=default_contract_validator,
        help="Path to check_template_contract.py.",
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=default_contract,
        help="Path to runner-template-contract.yaml.",
    )
    args = parser.parse_args()

    validator = args.validator.resolve()
    if not validator.is_file():
        sys.stderr.write(f"error: validator not found: {validator}\n")
        return 2
    contract_validator = args.contract_validator.resolve()
    if not contract_validator.is_file():
        sys.stderr.write(f"error: contract validator not found: {contract_validator}\n")
        return 2
    contract = args.contract.resolve()
    if not contract.is_file():
        sys.stderr.write(f"error: contract not found: {contract}\n")
        return 2

    fixtures, discovery_errors = discover_fixtures(
        args.fixtures_root.resolve(), EXPECTED_BAD_FAILURES
    )
    if discovery_errors:
        for error in discovery_errors:
            sys.stderr.write(f"error: {error}\n")
        return 2
    contract_fixtures, contract_discovery_errors = discover_fixtures(
        args.contract_fixtures_root.resolve(), EXPECTED_BAD_CONTRACT_FAILURES
    )
    if contract_discovery_errors:
        for error in contract_discovery_errors:
            sys.stderr.write(f"error: {error}\n")
        return 2

    caller_rc = run_fixtures(fixtures, validator, repo_root)
    contract_rc = run_contract_fixtures(
        contract_fixtures, contract_validator, contract, repo_root
    )
    malformed_contract_rc = run_malformed_contract_check(
        contract_fixtures, contract_validator, contract, repo_root
    )
    return caller_rc or contract_rc or malformed_contract_rc


if __name__ == "__main__":
    sys.exit(main())
