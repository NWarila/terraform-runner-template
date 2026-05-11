#!/usr/bin/env python3
"""Exercise check_template_contract.py repo-type inference."""

from __future__ import annotations

import sys
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from check_template_contract import detect_repo_type


@dataclass(frozen=True)
class Case:
    name: str
    builder: str
    cli_type: str | None
    expected_type: str | None
    expected_detail: str


CASES = (
    Case("runner-only", "runner", None, "runner", "repos/public|private"),
    Case("framework-only", "framework", None, "framework", "terraform/versions.tf"),
    Case("template-only", "template", None, "template", "template contract/tooling"),
    Case("template-plus-runner", "template-runner", None, None, "ambiguous repo type"),
    Case("framework-plus-runner", "framework-runner", None, None, "ambiguous repo type"),
    Case("cli-overrides-ambiguity", "template-runner", "template", "template", "--type CLI flag"),
)


def main() -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="repo-type-tests-") as raw_tmp:
        tmp = Path(raw_tmp)
        for case in CASES:
            repo = tmp / case.name
            build_fixture(repo, case.builder)
            repo_type, detail = detect_repo_type(repo, case.cli_type)
            passed = repo_type == case.expected_type and case.expected_detail in detail
            marker = "PASS" if passed else "FAIL"
            print(f"[{marker}] {case.name}: type={repo_type!r}; detail={detail}")
            if not passed:
                failures.append(
                    f"{case.name}: expected {case.expected_type!r} with "
                    f"{case.expected_detail!r}"
                )
        framework_cli = tmp / "framework-cli-contract-validation"
        build_fixture(framework_cli, "framework")
        completed = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).with_name("check_template_contract.py")),
                "--repo-root",
                str(framework_cli),
                "--contract",
                str(Path(__file__).parents[1] / "contract" / "runner-template-contract.yaml"),
                "--type",
                "framework",
            ],
            capture_output=True,
            check=False,
            text=True,
        )
        passed = (
            completed.returncode != 0
            and "not validated by this contract" in completed.stderr
        )
        marker = "PASS" if passed else "FAIL"
        print(f"[{marker}] framework-cli-contract-validation")
        if not passed:
            failures.append("--type framework should not run this contract validator")

    if failures:
        for failure in failures:
            print(f"error: {failure}", file=sys.stderr)
        return 1
    return 0


def build_fixture(repo: Path, kind: str) -> None:
    repo.mkdir(parents=True)
    if "template" in kind:
        touch(repo / "contract" / "runner-template-contract.yaml")
        touch(repo / "tools" / "check_template_contract.py")
        touch(repo / ".github" / "workflows" / "ci.yaml")
        touch(repo / ".github" / "workflows" / "reusable-terraform-validation.yaml")
    if "framework" in kind:
        touch(repo / "terraform" / "versions.tf")
    if "runner" in kind:
        (repo / "repos" / "public").mkdir(parents=True)


def touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
