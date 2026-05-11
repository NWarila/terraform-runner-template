#!/usr/bin/env python3
"""Ensure baselined command surfaces do not reference unbaselined tools."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "baseline-manifest.json"
SCAN_SURFACES = ("Makefile", ".pre-commit-config.yaml", "tools/verify.py")
TOOL_REFERENCE = re.compile(
    r"(?<![A-Za-z0-9_.\-/])"
    r"(tools/(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:py|sh))"
    r"(?![A-Za-z0-9_.\-/])"
)


def fail(message: str) -> None:
    raise SystemExit(f"manifest-self-consistency: {message}")


def manifest_items(raw: dict[str, Any]) -> list[dict[str, Any]]:
    version = raw.get("version")
    if version == "1":
        items = raw.get("files")
    elif version == "2":
        items = raw.get("byte_identical")
    else:
        fail(f"unsupported manifest version: {version!r}")
    if not isinstance(items, list):
        fail("manifest file list is not a list")
    return items


def manifest_paths() -> set[str]:
    try:
        raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"baseline-manifest.json is not valid JSON: {exc}")
    if not isinstance(raw, dict):
        fail("baseline-manifest.json root is not an object")

    paths: set[str] = set()
    for idx, item in enumerate(manifest_items(raw)):
        if not isinstance(item, dict):
            fail(f"manifest entry {idx} is not an object")
        for field in ("source", "target"):
            value = item.get(field)
            if isinstance(value, str):
                paths.add(value)
    return paths


def references_from(surface: Path) -> set[str]:
    text = surface.read_text(encoding="utf-8")
    references = {match.group(1) for match in TOOL_REFERENCE.finditer(text)}

    # Some surfaces intentionally glob shell helpers. Treat that as a reference
    # to every current helper so new scripts cannot be used without mirroring.
    if '"tools" / "ci").glob("*.sh")' in text or "'tools' / 'ci').glob('*.sh')" in text:
        references.update(
            path.relative_to(ROOT).as_posix() for path in (ROOT / "tools" / "ci").glob("*.sh")
        )
    return references


def main() -> None:
    baselined = manifest_paths()
    missing_surfaces = [path for path in SCAN_SURFACES if path not in baselined]
    if missing_surfaces:
        fail(f"scan surface(s) not mirrored by manifest: {missing_surfaces}")

    references: set[str] = set()
    for relative in SCAN_SURFACES:
        path = ROOT / relative
        if not path.is_file():
            fail(f"scan surface missing on disk: {relative}")
        references.update(references_from(path))

    missing = sorted(reference for reference in references if reference not in baselined)
    if missing:
        fail(f"referenced tool(s) missing from manifest: {missing}")
    print(f"manifest self-consistency: checked {len(references)} referenced tool(s)")


if __name__ == "__main__":
    main()
