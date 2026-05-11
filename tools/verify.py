#!/usr/bin/env python3
"""Cross-platform verification entrypoint for the runner template."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
YAMLLINT_CONFIG = (
    "{ extends: relaxed, rules: { line-length: disable, document-start: disable, "
    "comments: disable, truthy: {check-keys: false} } }"
)


Step = Callable[[], None]


def run(args: list[str], *, input_text: str | None = None) -> None:
    print("+ " + " ".join(args), flush=True)
    try:
        completed = subprocess.run(
            args,
            cwd=ROOT,
            input=input_text,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise SystemExit(f"missing executable: {args[0]}") from exc
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def capture(args: list[str], *, input_text: str | None = None) -> str:
    print("+ " + " ".join(args), flush=True)
    try:
        completed = subprocess.run(
            args,
            cwd=ROOT,
            capture_output=True,
            input=input_text,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise SystemExit(f"missing executable: {args[0]}") from exc
    if completed.returncode != 0:
        sys.stdout.write(completed.stdout)
        sys.stderr.write(completed.stderr)
        raise SystemExit(completed.returncode)
    return completed.stdout


def install(package: str) -> None:
    if os.environ.get("CI", "").lower() != "true":
        print(f"local run: not installing {package}; expecting it to be available", flush=True)
        return
    run([PYTHON, "-m", "pip", "install", "--no-cache-dir", package])


def opa_policy() -> None:
    opa_input = capture([PYTHON, "tools/build_opa_input.py"])
    run(
        [
            "opa",
            "eval",
            "--fail-defined",
            "--format",
            "pretty",
            "--stdin-input",
            "--data",
            "policies/opa",
            "data.repo_hygiene.deny[_]",
        ],
        input_text=opa_input,
    )


def opa_plan() -> None:
    fixture = ROOT / "tests" / "fixtures" / "terraform-plan" / "safe-plan.json"
    if not fixture.is_file():
        raise SystemExit(f"missing Terraform plan fixture: {fixture}")
    opa_input = capture([PYTHON, "tools/build_plan_input.py", "--plan-json", str(fixture)])
    run(
        [
            "opa",
            "eval",
            "--fail-defined",
            "--format",
            "pretty",
            "--stdin-input",
            "--data",
            "policies/opa",
            "data.terraform_plan.deny[_]",
        ],
        input_text=opa_input,
    )


def run_if_available(executable: str, args: list[str]) -> None:
    resolved = shutil.which(executable)
    if resolved is None:
        print(f"skip: {executable} not found on PATH", flush=True)
        return
    try:
        run([resolved, *args])
    except SystemExit as exc:
        if str(exc).startswith("missing executable:"):
            print(f"skip: {executable} could not be launched", flush=True)
            return
        raise


def contract_shape() -> None:
    install("pyyaml==6.0.3")
    import yaml

    spec = yaml.safe_load((ROOT / "contract/runner-template-contract.yaml").read_text())
    assert spec["version"] == "2", f"unexpected contract version: {spec.get('version')}"
    assert "universal" in spec, "missing universal block"
    assert "runner" in spec["types"], "missing runner type"
    assert "template" in spec["types"], "missing template type"
    assert "workflow_pinning" in spec, "missing workflow_pinning"
    print("runner-template contract looks well-formed")


def build_steps(case: str, framework_source: str) -> dict[str, Step]:
    return {
        "ruff": lambda: (
            install("ruff==0.13.0"),
            run([PYTHON, "-m", "ruff", "check", "tools/"]),
        ),
        "yamllint": lambda: (
            install("yamllint==1.35.1"),
            run(
                [
                    PYTHON,
                    "-m",
                    "yamllint",
                    "-d",
                    YAMLLINT_CONFIG,
                    ".github/workflows/",
                    "contract/",
                ]
            ),
        ),
        "actionlint": lambda: run_if_available("actionlint", [".github/workflows"]),
        "shellcheck": lambda: run_if_available("shellcheck", ["tools/install_ci_tools.sh"]),
        "markdownlint": lambda: run_if_available("markdownlint-cli2", ["**/*.md"]),
        "opa-test": lambda: run(["opa", "test", "policies/opa"]),
        "opa-policy": opa_policy,
        "opa-plan": opa_plan,
        "manifest-check": lambda: run([PYTHON, "tools/check_baseline_manifest.py"]),
        "contract-shape": contract_shape,
        "contract-check": lambda: (
            contract_shape(),
            run(
                [
                    PYTHON,
                    "tools/check_template_contract.py",
                    "--repo-root",
                    ".",
                    "--contract",
                    "contract/runner-template-contract.yaml",
                    "--type",
                    "template",
                ]
            ),
            run([PYTHON, "tools/run_repo_type_tests.py"]),
            run([PYTHON, "tools/run_contract_tests.py"]),
        ),
        "contract-tests": lambda: (
            install("pyyaml==6.0.3"),
            run([PYTHON, "tools/run_repo_type_tests.py"]),
            run([PYTHON, "tools/run_contract_tests.py"]),
        ),
        "docs-check": lambda: run([PYTHON, "tools/check_docs_layout.py"]),
        "adr-schema": lambda: run([PYTHON, "tools/check_adr_schema.py"]),
        "consistency-check": lambda: run([PYTHON, "tools/check_consistency.py"]),
        "integration": lambda: run(
            [
                PYTHON,
                "tools/ci/run_integration.py",
                "--case",
                case,
                "--framework-source",
                framework_source,
            ]
        ),
    }


TARGETS: dict[str, tuple[str, ...]] = {
    "lint": ("ruff", "yamllint", "actionlint", "shellcheck", "markdownlint"),
    "policy": ("opa-test", "opa-policy", "opa-plan"),
    "ci": (
        "lint",
        "policy",
        "docs-check",
        "adr-schema",
        "consistency-check",
        "manifest-check",
        "contract-check",
    ),
    "verify": ("ci", "integration"),
}


def execute(name: str, steps: dict[str, Step]) -> None:
    if name in TARGETS:
        for child in TARGETS[name]:
            execute(child, steps)
        return
    steps[name]()


def main() -> int:
    choices = sorted(set(TARGETS) | set(build_steps("basic", "../terraform-framework-template/terraform")))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", nargs="?", default="verify", choices=choices)
    parser.add_argument("--case", default="basic", help="Integration case to run.")
    parser.add_argument(
        "--framework-source",
        default="../terraform-framework-template/terraform",
        help="Framework terraform/ directory used by integration.",
    )
    args = parser.parse_args()

    execute(args.target, build_steps(args.case, args.framework_source))
    return 0


if __name__ == "__main__":
    sys.exit(main())
