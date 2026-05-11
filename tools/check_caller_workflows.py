#!/usr/bin/env python3
"""Check caller workflows for SHA-pinned external references."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


SHA_RE = re.compile(r"^[0-9a-f]{40}$")
USES_RE = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)")
PINNED_INPUT_RE = re.compile(r"^\s*(template_ref|framework_ref):\s*([^\s#]+)")


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    detail: str


def is_pinned_uses(value: str) -> bool:
    if value.startswith("./"):
        return True
    if value.startswith("docker://"):
        return "@sha256:" in value
    if "@" not in value:
        return False
    _, ref = value.rsplit("@", 1)
    return SHA_RE.match(ref) is not None


def scan_workflow(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        uses = USES_RE.match(line)
        if uses and not is_pinned_uses(uses.group(1)):
            findings.append(
                Finding(path, line_no, f"`uses:` is not SHA-pinned: {uses.group(1)}")
            )

        pinned_input = PINNED_INPUT_RE.match(line)
        if pinned_input and SHA_RE.match(pinned_input.group(2)) is None:
            findings.append(
                Finding(
                    path,
                    line_no,
                    f"{pinned_input.group(1)} must be a 40-character SHA",
                )
            )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()

    workflows = args.repo_root / ".github" / "workflows"
    if not workflows.is_dir():
        sys.stderr.write(f"error: workflow directory not found: {workflows}\n")
        return 2

    paths = sorted(workflows.glob("*.yml")) + sorted(workflows.glob("*.yaml"))
    findings = [finding for path in paths for finding in scan_workflow(path)]
    for finding in findings:
        rel = finding.path.relative_to(args.repo_root).as_posix()
        print(f"[FAIL] {rel}:{finding.line} - {finding.detail}")

    if findings:
        print(f"summary: {len(findings)} unpinned reference(s)")
        return 1

    print(f"summary: checked {len(paths)} workflow(s); all external refs are pinned")
    return 0


if __name__ == "__main__":
    sys.exit(main())
