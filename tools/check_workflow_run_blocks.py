#!/usr/bin/env python3
"""Syntax-check GitHub Actions bash run blocks."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path


RUN_LINE = re.compile(r"^(?P<indent>\s*)(?:-\s*)?run:\s*(?P<value>.*)$")
GITHUB_EXPRESSION = re.compile(r"\$\{\{.*?\}\}")
BLOCK_SCALARS = {"|", "|-", "|+", ">", ">-", ">+"}


@dataclass(frozen=True)
class RunBlock:
    path: Path
    line: int
    script: str


def iter_workflows(paths: list[Path]) -> list[Path]:
    workflows: list[Path] = []
    for path in paths:
        if path.is_dir():
            workflows.extend(sorted(path.glob("*.yaml")))
            workflows.extend(sorted(path.glob("*.yml")))
        else:
            workflows.append(path)
    return sorted(set(workflows))


def indentation(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def collect_run_blocks(path: Path) -> list[RunBlock]:
    lines = path.read_text(encoding="utf-8").splitlines()
    blocks: list[RunBlock] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        match = RUN_LINE.match(line)
        if match is None:
            index += 1
            continue

        run_line_no = index + 1
        run_indent = len(match.group("indent"))
        value = match.group("value").strip()
        if value not in BLOCK_SCALARS:
            if value:
                blocks.append(RunBlock(path=path, line=run_line_no, script=value))
            index += 1
            continue

        body: list[str] = []
        index += 1
        while index < len(lines):
            candidate = lines[index]
            if candidate.strip() and indentation(candidate) <= run_indent:
                break
            body.append(candidate)
            index += 1
        blocks.append(
            RunBlock(
                path=path,
                line=run_line_no,
                script=textwrap.dedent("\n".join(body)).strip(),
            )
        )

    return blocks


def default_bash() -> str:
    if os.name == "nt":
        git_bash = Path("C:/Program Files/Git/bin/bash.exe")
        if git_bash.is_file():
            return str(git_bash)
    return shutil.which("bash") or "bash"


def sanitize(script: str) -> str:
    return GITHUB_EXPRESSION.sub("GITHUB_EXPRESSION", script)


def check_block(block: RunBlock, bash: str) -> str | None:
    if not block.script:
        return None
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".sh", delete=False) as tmp:
        tmp.write(sanitize(block.script))
        tmp_path = Path(tmp.name)
    try:
        completed = subprocess.run(
            [bash, "-n", str(tmp_path)],
            capture_output=True,
            check=False,
            text=True,
        )
    finally:
        tmp_path.unlink(missing_ok=True)

    if completed.returncode == 0:
        return None
    detail = completed.stderr.strip() or completed.stdout.strip()
    return f"{block.path}:{block.line}: bash -n failed: {detail}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path, help="Workflow files or directories.")
    parser.add_argument("--bash", default=default_bash(), help="Bash executable to use.")
    args = parser.parse_args()

    failures: list[str] = []
    block_count = 0
    for workflow in iter_workflows(args.paths):
        for block in collect_run_blocks(workflow):
            block_count += 1
            failure = check_block(block, args.bash)
            if failure is not None:
                failures.append(failure)

    if failures:
        print("workflow run block syntax errors:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    print(f"workflow run blocks parse as bash: {block_count} checked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
