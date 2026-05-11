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


EXPECTED_BAD_FAILURES: dict[str, tuple[str, ...]] = {
    "bad-apply-unrestricted": ("terraform-deploy:input:apply",),
    "bad-framework-ref-mismatch": (
        "terraform-deploy:framework-ref_matches_pr_validation",
    ),
    "bad-overlay-destination": ("input:overlay_paths",),
    "bad-template-ref-mismatch": ("input:template_ref_matches_reusable",),
    "bad-template-ref-tag": (
        "pr-validation:runner-template-ref",
        "input:template_ref_sha",
    ),
    "bad-tfvars-traversal": ("terraform-deploy:input:tfvars_file",),
}

EXPECTED_BAD_CONTRACT_FAILURES: dict[str, tuple[str, ...]] = {
    "bad-deploy-missing-framework-reusable": (
        "content:.github/workflows/terraform-deploy.yaml:"
        "NWarila/terraform-framework-template/.github/workflows/reusable-terraform-deploy.yaml@[0-9a-f]{40}",
    ),
}


@dataclass(frozen=True)
class Fixture:
    name: str
    path: Path
    should_pass: bool
    expected_failures: tuple[str, ...] = ()


@dataclass(frozen=True)
class FixtureRun:
    fixture: Fixture
    returncode: int
    stdout: str
    stderr: str
    passed: bool
    detail: str


def discover_fixtures(
    fixtures_root: Path, expected_failures: dict[str, tuple[str, ...]]
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
        expected_failure_lines = [f"[FAIL] {name}" for name in fixture.expected_failures]
        missing = [
            line for line in expected_failure_lines if line not in completed.stdout
        ]
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
    shutil.copytree(fixture.path, target, dirs_exist_ok=True)
    return target


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
        expected_failure_lines = [f"[FAIL] {name}" for name in fixture.expected_failures]
        missing = [
            line for line in expected_failure_lines if line not in completed.stdout
        ]
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
    return caller_rc or contract_rc


if __name__ == "__main__":
    sys.exit(main())
