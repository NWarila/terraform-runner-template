#!/usr/bin/env python3
"""Enforce repository-wide naming consistency for framework references."""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_FRAMEWORK_REPO = "terraform-framework-template"
HISTORICAL_FRAMEWORK_REPO = "github-" + "terraform-framework"

STALE_PATTERNS = {
    "terraform-framework-" + "example": (
        f"use {CANONICAL_FRAMEWORK_REPO}; the old example repo name is stale"
    ),
    "nwarila-platform/" + HISTORICAL_FRAMEWORK_REPO: (
        f"use NWarila/{CANONICAL_FRAMEWORK_REPO}; the owner-qualified old repo is stale"
    ),
    HISTORICAL_FRAMEWORK_REPO: (
        f"use {CANONICAL_FRAMEWORK_REPO}, unless this is an org ADR historical note"
    ),
}

ORG_ADR_HISTORICAL_REFERENCES = {
    Path("docs/decision-records/org/0002-adopt-diataxis-documentation-framework.md"),
    Path("docs/decision-records/org/0003-use-deny-all-gitignore-strategy.md"),
}


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    column: int
    term: str
    guidance: str


def rel(path: Path) -> Path:
    return path.relative_to(ROOT)


def git_files() -> list[Path]:
    completed = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        return []

    paths: list[Path] = []
    for raw in completed.stdout.split(b"\0"):
        if not raw:
            continue
        paths.append(ROOT / raw.decode("utf-8"))
    return sorted(paths)


def fallback_files() -> list[Path]:
    ignored_dirs = {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".terraform",
        ".venv",
        "__pycache__",
        "node_modules",
    }
    paths: list[Path] = []
    for path in ROOT.rglob("*"):
        if any(part in ignored_dirs for part in path.relative_to(ROOT).parts):
            continue
        if path.is_file():
            paths.append(path)
    return sorted(paths)


def candidate_files() -> list[Path]:
    return [path for path in (git_files() or fallback_files()) if path.is_file()]


def is_allowed_historical_reference(path: Path, term: str) -> bool:
    return term == HISTORICAL_FRAMEWORK_REPO and rel(path) in ORG_ADR_HISTORICAL_REFERENCES


def scan_file(path: Path) -> list[Finding]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []

    findings: list[Finding] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for term, guidance in STALE_PATTERNS.items():
            if is_allowed_historical_reference(path, term):
                continue
            for match in re.finditer(re.escape(term), line):
                findings.append(
                    Finding(
                        path=rel(path),
                        line=line_number,
                        column=match.start() + 1,
                        term=term,
                        guidance=guidance,
                    )
                )
    return findings


def main() -> int:
    findings: list[Finding] = []
    for path in candidate_files():
        findings.extend(scan_file(path))

    if findings:
        print("consistency check failed:")
        for finding in findings:
            print(
                f"- {finding.path.as_posix()}:{finding.line}:{finding.column}: "
                f"found {finding.term!r}; {finding.guidance}"
            )
        return 1

    print("consistency check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
