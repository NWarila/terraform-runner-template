#!/usr/bin/env python3
"""Enforce zero drift between this template and its sibling runner template(s).

The validator + contract harness in this template are intentionally
~95% identical to their counterparts in `terraform-runner-template`.
A small set of regions are stack-specific (inventory paths, contract
filename, EXPECTED_BAD_CONTRACT_FAILURES per-fixture marker table,
the prune-paths set). Everything outside those regions MUST stay
byte-identical so a maintainer who improves the validator harness in
one template can trust that the improvement propagates to the others.

This check fetches each shape-shared file from the sibling at the
sibling's `main`, strips both copies of their intentional-difference
regions using anchored regex slicers, and byte-compares what remains.
Any drift exits non-zero with a unified diff for review.

Usage:
  python tools/check_cross_template_drift.py

CI invokes this on every PR and on a weekly schedule. A maintainer
intentionally changing a shape-shared region must change it in BOTH
templates in the same review window.
"""
from __future__ import annotations

import difflib
import json
import os
import re
import subprocess
import sys
from base64 import b64decode
from dataclasses import dataclass


# Set per template via env var on invocation (CI workflow passes it).
# This keeps the script file itself byte-identical between templates;
# only the env var differs, which is enforced by the matching CI job
# in each template.
SIBLING_REPO = os.environ.get("CROSS_TEMPLATE_SIBLING_REPO", "")
SIBLING_REF = os.environ.get("CROSS_TEMPLATE_SIBLING_REF", "main")

if not SIBLING_REPO:
    sys.stderr.write(
        "error: CROSS_TEMPLATE_SIBLING_REPO env var is required\n"
        "       (e.g. NWarila/terraform-runner-template)\n"
    )
    sys.exit(2)


@dataclass(frozen=True)
class StripPattern:
    """A region in the source that is intentionally template-specific."""

    label: str
    # Anchor: a regex that matches the line beginning the region.
    start: re.Pattern[str]
    # End: a regex that matches the line ending the region (inclusive).
    end: re.Pattern[str]


@dataclass(frozen=True)
class ShapeSharedFile:
    """One file pair that must stay byte-identical after stripping."""

    local_path: str
    sibling_path: str
    strip_regions: tuple[StripPattern, ...]


# --- Strip regions per file ---------------------------------------------------
#
# Each StripPattern's `start` matches the first line of an intentionally-
# stack-specific block; `end` matches the last line of that block. The
# check removes those line ranges from BOTH copies before comparing.
#
# When you legitimately change one of these regions, update both
# templates' versions in lockstep (the regex stays the same; only the
# enclosed content changes).

VALIDATOR_STRIPS: tuple[StripPattern, ...] = (
    StripPattern(
        label="docstring filename reference",
        start=re.compile(r'^The contract is defined in '),
        end=re.compile(r'^The contract is defined in '),
    ),
    StripPattern(
        label="inventory_files() function body",
        start=re.compile(r'^def inventory_files\(repo_root: Path\) -> list\[Path\]:'),
        end=re.compile(r'^    return sorted\(set\(paths\)\)'),
    ),
    StripPattern(
        label="default --contract argparse path",
        start=re.compile(r'^        / "contract"'),
        end=re.compile(r'-template-contract\.yaml",$'),
    ),
)

HARNESS_STRIPS: tuple[StripPattern, ...] = (
    StripPattern(
        label="EXPECTED_BAD_CONTRACT_FAILURES dict literal",
        start=re.compile(r'^EXPECTED_BAD_CONTRACT_FAILURES: dict\['),
        end=re.compile(r'^\}\s*$'),
    ),
    StripPattern(
        label="EXPECTED_BAD_FAILURES dict literal",
        start=re.compile(r'^EXPECTED_BAD_FAILURES: dict\['),
        end=re.compile(r'^\}\s*$'),
    ),
    StripPattern(
        label="default_contract path computation",
        start=re.compile(r'^    default_contract = repo_root / "contract" /'),
        end=re.compile(r'^    default_contract = repo_root / "contract" /'),
    ),
    StripPattern(
        label="prune_template_only_runner_paths() prune list",
        start=re.compile(r'^    for rel in '),
        end=re.compile(r'^    for rel in '),
    ),
    StripPattern(
        label="malformed_contract temp filename",
        start=re.compile(r'^        malformed_contract = temp_root / '),
        end=re.compile(r'^        malformed_contract = temp_root / '),
    ),
    StripPattern(
        label="--contract argparse help text",
        start=re.compile(r'^        help="Path to .*-template-contract\.yaml\."'),
        end=re.compile(r'^        help="Path to .*-template-contract\.yaml\."'),
    ),
)

SHAPE_SHARED: tuple[ShapeSharedFile, ...] = (
    ShapeSharedFile(
        local_path="tools/check_template_contract.py",
        sibling_path="tools/check_template_contract.py",
        strip_regions=VALIDATOR_STRIPS,
    ),
    ShapeSharedFile(
        local_path="tools/run_contract_tests.py",
        sibling_path="tools/run_contract_tests.py",
        strip_regions=HARNESS_STRIPS,
    ),
)


def fetch_sibling(path: str) -> str:
    """Return the sibling repo's file content at SIBLING_REF, as a string."""
    result = subprocess.run(
        ["gh", "api", f"repos/{SIBLING_REPO}/contents/{path}?ref={SIBLING_REF}"],
        capture_output=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    if payload.get("encoding") == "base64" and payload.get("content"):
        return b64decode(payload["content"]).decode("utf-8")
    raise RuntimeError(
        f"unexpected gh api response shape for {SIBLING_REPO}@{SIBLING_REF}:{path}"
    )


def strip_regions(text: str, patterns: tuple[StripPattern, ...]) -> str:
    """Remove every `[start, end]` line range matched by any pattern."""
    lines = text.splitlines(keepends=True)
    output: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = False
        for p in patterns:
            if p.start.search(line):
                # Find the end line (inclusive). Anchored search starting from i.
                j = i
                while j < n and not p.end.search(lines[j]):
                    j += 1
                # If we found an end, replace the whole range with a marker.
                if j < n:
                    output.append(f"# [stripped region: {p.label}]\n")
                    i = j + 1
                    stripped = True
                    break
        if not stripped:
            output.append(line)
            i += 1
    return "".join(output)


def diff_files(file_pair: ShapeSharedFile) -> str | None:
    """Return a unified diff if drift is detected, else None."""
    with open(file_pair.local_path, encoding="utf-8") as f:
        local_text = f.read()
    sibling_text = fetch_sibling(file_pair.sibling_path)

    local_stripped = strip_regions(local_text, file_pair.strip_regions)
    sibling_stripped = strip_regions(sibling_text, file_pair.strip_regions)

    if local_stripped == sibling_stripped:
        return None

    diff = difflib.unified_diff(
        sibling_stripped.splitlines(keepends=True),
        local_stripped.splitlines(keepends=True),
        fromfile=f"{SIBLING_REPO}:{file_pair.sibling_path} (sibling, stripped)",
        tofile=f"local:{file_pair.local_path} (this template, stripped)",
        n=3,
    )
    return "".join(diff)


def main() -> int:
    print(f"checking shape-shared files against {SIBLING_REPO}@{SIBLING_REF}")
    failures: list[tuple[str, str]] = []

    for pair in SHAPE_SHARED:
        print(f"  {pair.local_path} <-> {SIBLING_REPO}:{pair.sibling_path}")
        try:
            diff = diff_files(pair)
        except subprocess.CalledProcessError as exc:
            sys.stderr.write(
                f"error: failed to fetch sibling file via gh api: "
                f"{exc.stderr.decode('utf-8', 'replace')[:400]}\n"
            )
            return 2

        if diff is None:
            print("    [PASS] no drift in shape-shared regions")
        else:
            print("    [FAIL] drift detected")
            failures.append((pair.local_path, diff))

    if failures:
        print()
        print(f"=== DRIFT DETECTED ({len(failures)} file(s)) ===")
        for path, diff in failures:
            print()
            print(f"### {path}")
            print(diff)
        print()
        print(
            "Resolution: either change both templates' versions in sync, or "
            "extend the strip-region list in tools/check_cross_template_drift.py "
            "(if the drift is a NEW intentional difference and the change has "
            "been made symmetrically in both templates with the matching anchor)."
        )
        return 1

    print()
    print(f"summary: {len(SHAPE_SHARED)} shape-shared pair(s) clean, no drift")
    return 0


if __name__ == "__main__":
    sys.exit(main())
