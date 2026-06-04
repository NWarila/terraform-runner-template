#!/usr/bin/env python3
"""Cross-platform verification entrypoint for the runner template."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import shutil
import subprocess
import sys
import time
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


class ProcessMemoryCountersEx(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_ulong),
        ("PageFaultCount", ctypes.c_ulong),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
        ("PrivateUsage", ctypes.c_size_t),
    ]


def process_private_bytes(process: subprocess.Popen[str]) -> int | None:
    if os.name != "nt":
        return None
    counters = ProcessMemoryCountersEx()
    counters.cb = ctypes.sizeof(counters)
    handle = getattr(process, "_handle", None)
    if handle is None:
        return None
    ok = ctypes.windll.psapi.GetProcessMemoryInfo(
        ctypes.c_void_p(handle), ctypes.byref(counters), counters.cb
    )
    if not ok:
        return None
    return int(counters.PrivateUsage)


def run_opa(args: list[str], *, input_text: str | None = None) -> None:
    """Run OPA under a wall-clock timeout and (on Windows) a private-memory cap.

    A pathological Rego policy can drive ``opa eval`` to tens of GB of committed
    memory and hang the host. This bounds it so OPA aborts with a clear error
    instead of wedging the machine. Tunable via OPA_TIMEOUT_SECONDS and
    OPA_MAX_PRIVATE_MB environment variables.
    """
    timeout_seconds = int(os.environ.get("OPA_TIMEOUT_SECONDS", "30"))
    max_private_mb = int(os.environ.get("OPA_MAX_PRIVATE_MB", "1024"))
    max_private_bytes = max_private_mb * 1024 * 1024

    print("+ " + " ".join(args), flush=True)
    try:
        process = subprocess.Popen(
            args,
            cwd=ROOT,
            stdin=subprocess.PIPE if input_text is not None else None,
            text=True,
        )
    except FileNotFoundError as exc:
        raise SystemExit(f"missing executable: {args[0]}") from exc

    if input_text is not None and process.stdin is not None:
        process.stdin.write(input_text)
        process.stdin.close()

    deadline = time.monotonic() + timeout_seconds
    peak_private = 0
    killed_reason: str | None = None
    while process.poll() is None:
        private_bytes = process_private_bytes(process)
        if private_bytes is not None:
            peak_private = max(peak_private, private_bytes)
            if private_bytes > max_private_bytes:
                killed_reason = (
                    f"private memory exceeded {max_private_mb} MiB "
                    f"(observed {private_bytes // (1024 * 1024)} MiB)"
                )
                process.kill()
                break
        if time.monotonic() > deadline:
            killed_reason = f"timeout exceeded {timeout_seconds} seconds"
            process.kill()
            break
        time.sleep(0.1)

    returncode = process.wait()
    if killed_reason is not None:
        if peak_private:
            print(f"opa peak private memory: {peak_private // (1024 * 1024)} MiB")
        raise SystemExit(f"opa aborted: {killed_reason}")
    if returncode != 0:
        raise SystemExit(returncode)


def capture_opa(args: list[str], *, input_text: str | None = None) -> str:
    """Like capture(), but for OPA: bounded by the same timeout + memory cap as
    run_opa so a pathological policy cannot exhaust host memory while we read its
    output. Output is drained concurrently so a large result never deadlocks."""
    import threading

    timeout_seconds = int(os.environ.get("OPA_TIMEOUT_SECONDS", "30"))
    max_private_mb = int(os.environ.get("OPA_MAX_PRIVATE_MB", "1024"))
    max_private_bytes = max_private_mb * 1024 * 1024

    print("+ " + " ".join(args), flush=True)
    try:
        process = subprocess.Popen(
            args,
            cwd=ROOT,
            stdin=subprocess.PIPE if input_text is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as exc:
        raise SystemExit(f"missing executable: {args[0]}") from exc

    out_chunks: list[str] = []
    err_chunks: list[str] = []
    t_out = threading.Thread(target=lambda: out_chunks.append(process.stdout.read()), daemon=True)
    t_err = threading.Thread(target=lambda: err_chunks.append(process.stderr.read()), daemon=True)
    t_out.start()
    t_err.start()
    if input_text is not None and process.stdin is not None:
        try:
            process.stdin.write(input_text)
            process.stdin.close()
        except BrokenPipeError:
            pass

    deadline = time.monotonic() + timeout_seconds
    peak_private = 0
    killed_reason: str | None = None
    while process.poll() is None:
        private_bytes = process_private_bytes(process)
        if private_bytes is not None:
            peak_private = max(peak_private, private_bytes)
            if private_bytes > max_private_bytes:
                killed_reason = (
                    f"private memory exceeded {max_private_mb} MiB "
                    f"(observed {private_bytes // (1024 * 1024)} MiB)"
                )
                process.kill()
                break
        if time.monotonic() > deadline:
            killed_reason = f"timeout exceeded {timeout_seconds} seconds"
            process.kill()
            break
        time.sleep(0.1)

    returncode = process.wait()
    t_out.join(timeout=5)
    t_err.join(timeout=5)
    stdout = "".join(c for c in out_chunks if c)
    stderr = "".join(c for c in err_chunks if c)
    if killed_reason is not None:
        if peak_private:
            print(f"opa peak private memory: {peak_private // (1024 * 1024)} MiB")
        raise SystemExit(f"opa aborted: {killed_reason}")
    if returncode != 0:
        sys.stdout.write(stdout)
        sys.stderr.write(stderr)
        raise SystemExit(returncode)
    return stdout


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
    run_opa(
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
    output = capture_opa(
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


def run_required_tool(executable: str, args: list[str]) -> None:
    resolved = shutil.which(executable)
    if resolved is None:
        raise SystemExit(f"missing executable: {executable}")
    run([resolved, *args])


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
    run_required_tool("actionlint", workflow_files())


def shellcheck() -> None:
    run_required_tool("shellcheck", ["tools/install_ci_tools.sh"])


def markdownlint() -> None:
    run_required_tool("markdownlint-cli2", ["**/*.md"])


def workflow_helper_tests() -> None:
    shellcheck()
    run([PYTHON, "tools/check_workflow_run_blocks.py", ".github/workflows"])
    run([PYTHON, "tools/check_caller_workflows.py", "--repo-root", "."])
    privileged_workflows()


def privileged_workflows() -> None:
    install("pyyaml==6.0.3")
    run([PYTHON, "tools/check_privileged_workflows.py", "--repo-root", "."])
    run([PYTHON, "tools/run_privileged_workflow_tests.py"])


def opa_test() -> None:
    run_opa(["opa", "test", "policies/opa"])


def manifest_check() -> None:
    run([PYTHON, "tools/check_baseline_manifest.py", "--check-present-sources"])


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
        "privileged-workflows": privileged_workflows,
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
    "lint": ("ruff", "yamllint"),
    "policy": ("opa-test", "opa-policy", "opa-plan"),
    "ci": (
        "lint",
        "actionlint",
        "workflow-helper-tests",
        "policy",
        "markdownlint",
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
