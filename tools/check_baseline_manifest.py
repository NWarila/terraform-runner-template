"""Validate baseline-manifest.json without importing drift-gate."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any


def fail(message: str) -> None:
    raise SystemExit(f"manifest-check: {message}")


def manifest_path(field: str, value: Any) -> str:
    if not isinstance(value, str) or not value:
        fail(f"{field} must be a non-empty string")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        fail(f"{field} must be repo-rooted and must not contain '..': {value!r}")
    return value


def main() -> None:
    try:
        raw = json.loads(Path("baseline-manifest.json").read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"baseline-manifest.json is not valid JSON: {exc}")
    if not isinstance(raw, dict) or set(raw) != {"version", "files"}:
        fail("root must contain exactly 'version' and 'files'")
    if raw["version"] != "1":
        fail(f"unsupported manifest version: {raw['version']!r}")
    files = raw["files"]
    if not isinstance(files, list) or not files:
        fail("'files' must be a non-empty list")

    sources: list[str] = []
    targets: set[str] = set()
    for idx, item in enumerate(files):
        if not isinstance(item, dict) or set(item) != {"source", "target"}:
            fail(f"files[{idx}] must contain exactly 'source' and 'target'")
        source = manifest_path(f"files[{idx}].source", item["source"])
        target = manifest_path(f"files[{idx}].target", item["target"])
        if target in targets:
            fail(f"duplicate target path: {target!r}")
        sources.append(source)
        targets.add(target)

    missing = [source for source in sources if not Path(source).is_file()]
    if missing:
        fail(f"sources missing: {missing}")

    listed_sources = set(sources)
    template_adrs = sorted(
        path.as_posix()
        for path in (Path("docs") / "decision-records" / "template").glob("[0-9][0-9][0-9][0-9]-*.md")
    )
    unlisted_template_adrs = [path for path in template_adrs if path not in listed_sources]
    if unlisted_template_adrs:
        fail(f"template ADRs missing from baseline manifest: {unlisted_template_adrs}")

    print(f"manifest: version={raw['version']}, files={len(files)}")
    print("all sources resolve on disk")


if __name__ == "__main__":
    main()
