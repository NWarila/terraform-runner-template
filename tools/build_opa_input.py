#!/usr/bin/env python3
"""Build OPA input from this repository's real files.

The repo_hygiene policy expects a compact JSON document containing
workflow `uses:` references plus selected file contents. This script turns the
checked-out repo into that input so `opa eval` enforces policy against the
actual files under review, not only policy unit-test fixtures.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None


USES_LINE_RE = re.compile(r"^\s*(?:-\s*)?uses:\s*(.+?)\s*(?:#.*)?$")
TRUSTED_AUTHORS_ARRAY_RE = re.compile(
    r"declare\s+-a\s+trusted_authors\s*=\s*\((?P<body>.*?)\)",
    re.DOTALL,
)
QUOTED_STRING_RE = re.compile(r'"([^"]+)"|\'([^\']+)\'')
WORKFLOW_GLOBS = ("*.yml", "*.yaml")
POLICY_FILE_PATHS = ("terraform/versions.tf",)


def normalize_uses(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return value.strip()


def collect_workflow_uses(repo_root: Path) -> dict[str, list[dict[str, Any]]]:
    workflows_dir = repo_root / ".github" / "workflows"
    workflows: dict[str, list[dict[str, Any]]] = {}
    if not workflows_dir.is_dir():
        return workflows

    paths: list[Path] = []
    for pattern in WORKFLOW_GLOBS:
        paths.extend(workflows_dir.glob(pattern))

    for path in sorted(set(paths)):
        refs: list[dict[str, Any]] = []
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            match = USES_LINE_RE.match(line)
            if not match:
                continue
            refs.append({"line": line_no, "uses": normalize_uses(match.group(1))})
        if refs:
            workflows[path.relative_to(repo_root).as_posix()] = refs
    return workflows


def collect_workflow_files(repo_root: Path) -> dict[str, str]:
    workflows_dir = repo_root / ".github" / "workflows"
    files: dict[str, str] = {}
    if not workflows_dir.is_dir():
        return files

    paths: list[Path] = []
    for pattern in WORKFLOW_GLOBS:
        paths.extend(workflows_dir.glob(pattern))

    for path in sorted(set(paths)):
        files[path.relative_to(repo_root).as_posix()] = path.read_text(encoding="utf-8")
    return files


def require_yaml() -> Any:
    if yaml is None:
        sys.stderr.write(
            "error: PyYAML is required for structural workflow policy input.\n"
        )
        sys.exit(2)
    return yaml


def workflow_paths(repo_root: Path) -> list[Path]:
    workflows_dir = repo_root / ".github" / "workflows"
    if not workflows_dir.is_dir():
        return []
    paths: list[Path] = []
    for pattern in WORKFLOW_GLOBS:
        paths.extend(workflows_dir.glob(pattern))
    return sorted(set(paths))


def extract_trusted_authors(run: str) -> tuple[bool, list[str]]:
    match = TRUSTED_AUTHORS_ARRAY_RE.search(run)
    if not match:
        return False, []
    authors = [
        double or single
        for double, single in QUOTED_STRING_RE.findall(match.group("body"))
    ]
    return True, authors


def collect_run_blocks(workflow: dict[str, Any]) -> list[str]:
    jobs = workflow.get("jobs", {})
    if not isinstance(jobs, dict):
        return []
    runs: list[str] = []
    for job in jobs.values():
        if not isinstance(job, dict):
            continue
        steps = job.get("steps", [])
        if not isinstance(steps, list):
            continue
        for step in steps:
            if isinstance(step, dict) and isinstance(step.get("run"), str):
                runs.append(step["run"])
    return runs


def collect_workflow_data(repo_root: Path) -> dict[str, dict[str, Any]]:
    yaml_mod = require_yaml()
    data: dict[str, dict[str, Any]] = {}
    for path in workflow_paths(repo_root):
        rel = path.relative_to(repo_root).as_posix()
        workflow = yaml_mod.load(path.read_text(encoding="utf-8"), Loader=yaml_mod.BaseLoader)
        if not isinstance(workflow, dict):
            continue
        on_block = workflow.get("on", {})
        workflow_call = {}
        if isinstance(on_block, dict):
            workflow_call = on_block.get("workflow_call", {})
        workflow_call_inputs = []
        if isinstance(workflow_call, dict) and isinstance(workflow_call.get("inputs"), dict):
            workflow_call_inputs = sorted(workflow_call["inputs"])

        run_blocks = collect_run_blocks(workflow)
        trusted_authors: list[str] = []
        has_trusted_authors_array = False
        for run in run_blocks:
            found, authors = extract_trusted_authors(run)
            if found:
                has_trusted_authors_array = True
                trusted_authors.extend(authors)

        data[rel] = {
            "workflow_call_inputs": workflow_call_inputs,
            "has_trusted_authors_array": has_trusted_authors_array,
            "trusted_authors": trusted_authors,
        }
    return data


def collect_files(repo_root: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for rel in POLICY_FILE_PATHS:
        path = repo_root / rel
        if path.is_file():
            files[rel] = path.read_text(encoding="utf-8")
    files.update(collect_workflow_files(repo_root))
    return files


def build_input(repo_root: Path) -> dict[str, Any]:
    return {
        "workflows": collect_workflow_uses(repo_root),
        "workflow_data": collect_workflow_data(repo_root),
        "files": collect_files(repo_root),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root to inspect (default: current working directory).",
    )
    args = parser.parse_args()

    json.dump(build_input(args.repo_root.resolve()), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
