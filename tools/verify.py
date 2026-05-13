#!/usr/bin/env python3
"""Cross-platform verification entrypoint for the runner template."""

from __future__ import annotations

import argparse
import json
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
    install("pyyaml==6.0.3")
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
    safe_fixture = ROOT / "tests" / "fixtures" / "terraform-plan" / "safe-plan.json"
    bad_fixture = ROOT / "tests" / "fixtures" / "terraform-plan" / "bad-plan.json"
    if not safe_fixture.is_file():
        raise SystemExit(f"missing Terraform plan fixture: {safe_fixture}")
    if not bad_fixture.is_file():
        raise SystemExit(f"missing Terraform plan fixture: {bad_fixture}")
    safe_denies = opa_plan_denies(safe_fixture)
    if safe_denies:
        raise SystemExit(
            "safe Terraform plan fixture produced denial(s): "
            + "; ".join(safe_denies)
        )
    bad_denies = opa_plan_denies(bad_fixture)
    expected = (
        "aws_s3_bucket.public_logs must have server-side encryption configuration",
        "aws_security_group.admin must not expose admin port 22 to the world",
    )
    missing = [
        fragment
        for fragment in expected
        if not any(fragment in denial for denial in bad_denies)
    ]
    extra = [
        denial
        for denial in bad_denies
        if not any(fragment in denial for fragment in expected)
    ]
    if missing:
        raise SystemExit(
            "bad Terraform plan fixture did not produce expected denial(s): "
            + "; ".join(missing)
        )
    if extra:
        raise SystemExit(
            "bad Terraform plan fixture produced unexpected denial(s): "
            + "; ".join(extra)
        )
    print(f"Terraform plan policy fixtures passed: {len(bad_denies)} bad-plan denials")


def opa_plan_denies(fixture: Path) -> list[str]:
    opa_input = capture([PYTHON, "tools/build_plan_input.py", "--plan-json", str(fixture)])
    output = capture(
        [
            "opa",
            "eval",
            "--format",
            "json",
            "--stdin-input",
            "--data",
            "policies/opa",
            "data.terraform_plan.deny",
        ],
        input_text=opa_input,
    )
    payload = json.loads(output)
    result = payload.get("result", [])
    if not result:
        return []
    expressions = result[0].get("expressions", [])
    if not expressions:
        return []
    value = expressions[0].get("value", [])
    if not isinstance(value, list):
        return []
    return [str(denial) for denial in value]


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


def workflow_files() -> list[str]:
    workflows = ROOT / ".github" / "workflows"
    return sorted(
        path.relative_to(ROOT).as_posix()
        for pattern in ("*.yml", "*.yaml")
        for path in workflows.glob(pattern)
    )


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


def ruff() -> None:
    install("ruff==0.13.0")
    run([PYTHON, "-m", "ruff", "check", "tools/"])


def yamllint() -> None:
    install("yamllint==1.35.1")
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
    )


def actionlint() -> None:
    run_if_available("actionlint", workflow_files())


def shellcheck() -> None:
    run_if_available("shellcheck", ["tools/install_ci_tools.sh"])


def markdownlint() -> None:
    run_if_available("markdownlint-cli2", ["**/*.md"])


def workflow_helper_tests() -> None:
    shellcheck()
    run([PYTHON, "tools/check_workflow_run_blocks.py", ".github/workflows"])
    run([PYTHON, "tools/check_caller_workflows.py", "--repo-root", "."])
    contract_tests()


def opa_test() -> None:
    run(["opa", "test", "policies/opa"])


def manifest_check() -> None:
    run([PYTHON, "tools/check_baseline_manifest.py"])


def contract_check() -> None:
    contract_shape()
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
    )
    run([PYTHON, "tools/run_contract_tests.py"])


def contract_tests() -> None:
    install("pyyaml==6.0.3")
    run([PYTHON, "tools/run_contract_tests.py"])


def docs_check() -> None:
    run([PYTHON, "tools/check_docs_layout.py"])


def adr_schema() -> None:
    run([PYTHON, "tools/check_adr_schema.py"])


def make_integration_step(case: str, framework_source: str) -> Step:
    def integration() -> None:
        run(
            [
                PYTHON,
                "tools/ci/run_integration.py",
                "--case",
                case,
                "--framework-source",
                framework_source,
            ]
        )

    return integration


def build_steps(case: str, framework_source: str) -> dict[str, Step]:
    return {
        "ruff": ruff,
        "yamllint": yamllint,
        "actionlint": actionlint,
        "shellcheck": shellcheck,
        "markdownlint": markdownlint,
        "workflow-helper-tests": workflow_helper_tests,
        "opa-test": opa_test,
        "opa-policy": opa_policy,
        "opa-plan": opa_plan,
        "manifest-check": manifest_check,
        "contract-shape": contract_shape,
        "contract-check": contract_check,
        "contract-tests": contract_tests,
        "docs-check": docs_check,
        "adr-schema": adr_schema,
        "integration": make_integration_step(case, framework_source),
    }


TARGETS: dict[str, tuple[str, ...]] = {
    "lint": ("ruff", "yamllint", "actionlint", "markdownlint"),
    "policy": ("opa-test", "opa-policy", "opa-plan"),
    "ci": (
        "lint",
        "workflow-helper-tests",
        "policy",
        "docs-check",
        "adr-schema",
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
