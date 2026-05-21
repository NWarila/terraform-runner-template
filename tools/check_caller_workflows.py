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
OVERLAY_BLOCK_RE = re.compile(r"^(?P<indent>\s*)overlay_paths:\s*\|\s*(?:#.*)?$")
WINDOWS_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:[\\/]")
ALLOWED_OVERLAY_DESTINATIONS = (
    "terraform/repos",
    "terraform/fixtures/runtime",
)


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


def normalize_overlay_path(value: str) -> str:
    return value.replace("\\", "/").strip().rstrip("/")


def validate_overlay_path(kind: str, value: str) -> str | None:
    normalized = normalize_overlay_path(value)
    if not normalized:
        return f"overlay {kind} is empty"
    if normalized.startswith("/") or WINDOWS_ABSOLUTE_RE.match(normalized):
        return f"overlay {kind} must be relative: {value}"
    parts = [part for part in normalized.split("/") if part]
    if any(part in {".", ".."} for part in parts):
        return f"overlay {kind} must not contain path traversal: {value}"
    return None


def allowed_overlay_destination(value: str) -> bool:
    normalized = normalize_overlay_path(value)
    return any(
        normalized == allowed or normalized.startswith(f"{allowed}/")
        for allowed in ALLOWED_OVERLAY_DESTINATIONS
    )


def scan_overlay_paths(path: Path, lines: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    for idx, line in enumerate(lines):
        match = OVERLAY_BLOCK_RE.match(line)
        if not match:
            continue

        block_indent = len(match.group("indent"))
        for child_idx in range(idx + 1, len(lines)):
            raw = lines[child_idx]
            if not raw.strip():
                continue
            indent = len(raw) - len(raw.lstrip(" "))
            if indent <= block_indent:
                break

            entry = raw.split("#", 1)[0].strip()
            if not entry:
                continue
            if "=>" not in entry:
                findings.append(
                    Finding(
                        path,
                        child_idx + 1,
                        f"overlay entry missing '=>' separator: {entry}",
                    )
                )
                continue

            source, destination = (part.strip() for part in entry.split("=>", 1))
            for kind, value in (("source", source), ("destination", destination)):
                detail = validate_overlay_path(kind, value)
                if detail:
                    findings.append(Finding(path, child_idx + 1, detail))
            if destination and not allowed_overlay_destination(destination):
                findings.append(
                    Finding(
                        path,
                        child_idx + 1,
                        (
                            "overlay destination must be under terraform/repos/ "
                            "or terraform/fixtures/runtime/: "
                            f"{destination}"
                        ),
                    )
                )
    return findings


def scan_workflow(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    for line_no, line in enumerate(lines, 1):
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
    findings.extend(scan_overlay_paths(path, lines))
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
