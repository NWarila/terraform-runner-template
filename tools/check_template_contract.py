#!/usr/bin/env python3
"""Verify that a consumer repository conforms to the golden template contract.

The contract is defined in `contract/runner-template-contract.yaml`. This
script walks the repository under inspection and emits one PASS/FAIL line per
rule, exiting non-zero if any rule fails.

The contract has two layers:
  - Universal requirements (apply to every supported type).
  - Type-specific requirements: `runner` (data-only deployer that consumes a
    framework at runtime) or `template` (this type-template repository
    validating itself).

Repo type is explicit. Callers pass `--type runner` for consumers and
`--type template` for this template repository. Hybrid layouts should be
handled by choosing the contract surface being validated at the call site.

Usage:
    check_template_contract.py [--repo-root PATH] [--contract PATH]
                               [--template-root PATH]
                               --type runner|template
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


SHA_RE = re.compile(r"^[0-9a-f]{40}$")
USES_LINE_RE = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)")
CONTRACT_TYPES = ("runner", "template")


@dataclass
class RuleResult:
    name: str
    passed: bool
    detail: str = ""


def require_yaml():
    if yaml is None:
        sys.stderr.write(
            "error: PyYAML is required. Install with `pip install pyyaml`.\n"
        )
        sys.exit(2)
    return yaml


def resolve_exact_path(repo_root: Path, rel: str) -> Path | None:
    """Resolve rel only when every path component matches exact casing."""
    current = repo_root
    for part in Path(rel).parts:
        if part in ("", "."):
            continue
        try:
            matches = [entry for entry in current.iterdir() if entry.name == part]
        except FileNotFoundError:
            return None
        if not matches:
            return None
        current = matches[0]
    return current


def check_path(repo_root: Path, entry: dict) -> RuleResult:
    rel = entry["path"]
    target = resolve_exact_path(repo_root, rel)
    expected_dir = entry.get("type") == "directory"
    if target is None:
        ok = False
    elif expected_dir:
        ok = target.is_dir()
    else:
        ok = target.is_file()
    return RuleResult(
        name=f"path:{rel}",
        passed=ok,
        detail="" if ok else f"missing {'directory' if expected_dir else 'file'}",
    )


def entry_applies(entry: dict, repo_type: str) -> bool:
    applies_to = entry.get("applies_to")
    if applies_to is not None:
        if isinstance(applies_to, str):
            applies = {applies_to}
        else:
            applies = set(applies_to)
        if repo_type not in applies:
            print(
                f"[SKIP] {entry_label(entry)} - applies_to "
                f"{sorted(applies)} excludes {repo_type}"
            )
            return False

    except_types = entry.get("except_types")
    if except_types is not None:
        if isinstance(except_types, str):
            excluded = {except_types}
        else:
            excluded = set(except_types)
        if repo_type in excluded:
            print(
                f"[SKIP] {entry_label(entry)} - except_types "
                f"{sorted(excluded)} excludes {repo_type}"
            )
            return False

    return True


def entry_label(entry: dict) -> str:
    return entry.get("path") or entry.get("file") or entry.get("name") or "<entry>"


def check_content_rule(repo_root: Path, rule: dict) -> RuleResult:
    rel = rule["file"]
    pattern = rule["pattern"]
    must_match = rule["must_match"]
    target = repo_root / rel
    if not target.is_file():
        return RuleResult(
            name=f"content:{rel}:{pattern}",
            passed=False,
            detail="file not found",
        )
    text = target.read_text(encoding="utf-8")
    found = re.search(pattern, text) is not None
    ok = found == must_match
    detail = ""
    if not ok:
        if must_match:
            detail = "required pattern not found"
        else:
            detail = "forbidden pattern present"
    return RuleResult(
        name=f"content:{rel}:{pattern}",
        passed=ok,
        detail=detail,
    )


def check_workflow_pinning(repo_root: Path, settings: dict) -> list[RuleResult]:
    workflows_dir = repo_root / ".github" / "workflows"
    results: list[RuleResult] = []
    if not workflows_dir.is_dir():
        results.append(
            RuleResult(
                name="workflow_pinning",
                passed=False,
                detail=".github/workflows/ not found",
            )
        )
        return results

    allow_local = settings.get("allow_local_refs", True)
    allow_digest = settings.get("allow_docker_digest", True)

    for path in sorted(workflows_dir.glob("*.y*ml")):
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            m = USES_LINE_RE.match(line)
            if not m:
                continue
            ref = m.group(1)
            ok, detail = _classify_uses(
                ref, allow_local=allow_local, allow_digest=allow_digest
            )
            if not ok:
                results.append(
                    RuleResult(
                        name=f"pin:{path.name}:{lineno}",
                        passed=False,
                        detail=f"{ref} - {detail}",
                    )
                )
    if not results:
        results.append(RuleResult(name="workflow_pinning", passed=True))
    return results


def _classify_uses(ref: str, *, allow_local: bool, allow_digest: bool) -> tuple[bool, str]:
    if ref.startswith("./"):
        return (allow_local, "local reference disallowed" if not allow_local else "")
    if ref.startswith("docker://"):
        if "@sha256:" in ref:
            return (True, "")
        if allow_digest:
            return (False, "docker image not digest-pinned")
        return (False, "docker references disallowed")
    if "@" not in ref:
        return (False, "no version reference")
    _, version = ref.rsplit("@", 1)
    if SHA_RE.match(version):
        return (True, "")
    return (False, f"not SHA-pinned (got @{version})")


def check_sync_drift(
    repo_root: Path, template_root: Path, manifest: Path
) -> list[RuleResult]:
    """Verify that synced files in the consumer match the template byte-for-byte."""
    if manifest.is_file():
        spec = yaml.safe_load(manifest.read_text(encoding="utf-8"))
        entries = spec.get("synced_files", [])
    else:
        baseline = template_root / "baseline-manifest.json"
        if not baseline.is_file():
            return [
                RuleResult(
                    name="sync_drift",
                    passed=False,
                    detail=(
                        f"sync manifest not found at {manifest} and "
                        f"baseline manifest not found at {baseline}"
                    ),
                )
            ]
        try:
            spec = json.loads(baseline.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return [
                RuleResult(
                    name="sync_drift",
                    passed=False,
                    detail=f"baseline manifest is not valid JSON: {exc}",
                )
            ]
        entries = spec.get("files", [])
        if spec.get("version") != "1" or not isinstance(entries, list):
            return [
                RuleResult(
                    name="sync_drift",
                    passed=False,
                    detail="baseline manifest must use version 1 with a files list",
                )
            ]

    results: list[RuleResult] = []
    for entry in entries:
        if "path" in entry:
            source_rel = target_rel = entry["path"]
        elif "source" in entry and "target" in entry:
            source_rel = entry["source"]
            target_rel = entry["target"]
        else:
            results.append(
                RuleResult(
                    name="sync_drift:malformed-entry",
                    passed=False,
                    detail=f"entry missing path or source+target: {entry!r}",
                )
            )
            continue
        if entry.get("substitutions"):
            continue
        if entry.get("mode") == "create-if-missing":
            continue
        src = template_root / source_rel
        dst = repo_root / target_rel
        if not src.is_file():
            results.append(
                RuleResult(
                    name=f"sync_drift:{target_rel}",
                    passed=False,
                    detail=f"template source missing at {source_rel}",
                )
            )
            continue
        if not dst.is_file():
            results.append(
                RuleResult(
                    name=f"sync_drift:{target_rel}",
                    passed=False,
                    detail="consumer file missing - sync workflow has not run yet?",
                )
            )
            continue
        if src.read_bytes() != dst.read_bytes():
            results.append(
                RuleResult(
                    name=f"sync_drift:{target_rel}",
                    passed=False,
                    detail="content differs from template (manual edit? sync stale?)",
                )
            )
            continue
        results.append(RuleResult(name=f"sync_drift:{target_rel}", passed=True))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Root of the repository under inspection (default: cwd).",
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=Path(__file__).resolve().parent.parent
        / "contract"
        / "runner-template-contract.yaml",
        help="Path to the contract manifest YAML.",
    )
    parser.add_argument(
        "--template-root",
        type=Path,
        default=None,
        help=(
            "Root of the terraform-template checkout. When provided, enables "
            "sync-drift checks (byte-equality of synced files)."
        ),
    )
    parser.add_argument(
        "--type",
        choices=CONTRACT_TYPES,
        required=True,
        help="Contract surface to validate.",
    )
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    repo_type = args.type

    if not args.contract.is_file():
        sys.stderr.write(f"error: contract not found at {args.contract}\n")
        return 2

    yaml_mod = require_yaml()
    contract = yaml_mod.safe_load(args.contract.read_text(encoding="utf-8"))
    print(f"repo type: {repo_type} (--type)")
    print()

    universal = contract.get("universal", {})
    type_block = (contract.get("types") or {}).get(repo_type, {})

    results: list[RuleResult] = []

    for entry in universal.get("required_root_files", []):
        if not entry_applies(entry, repo_type):
            continue
        results.append(check_path(repo_root, entry))
    for entry in universal.get("required_github_files", []):
        if not entry_applies(entry, repo_type):
            continue
        results.append(check_path(repo_root, entry))
    for entry in universal.get("required_documentation", []):
        if not entry_applies(entry, repo_type):
            continue
        results.append(check_path(repo_root, entry))

    for entry in type_block.get("required_paths", []):
        if not entry_applies(entry, repo_type):
            continue
        results.append(check_path(repo_root, entry))
    for rule in type_block.get("content_rules", []):
        if not entry_applies(rule, repo_type):
            continue
        results.append(check_content_rule(repo_root, rule))

    pinning = contract.get("workflow_pinning")
    if pinning and pinning.get("enforce_sha_pin"):
        results.extend(check_workflow_pinning(repo_root, pinning))

    if args.template_root is not None:
        template_root = args.template_root.resolve()
        manifest = template_root / "sync" / "synced-files.yaml"
        results.extend(check_sync_drift(repo_root, template_root, manifest))

    failed = [r for r in results if not r.passed]
    for r in results:
        marker = "PASS" if r.passed else "FAIL"
        line = f"[{marker}] {r.name}"
        if r.detail:
            line += f" - {r.detail}"
        print(line)

    print()
    print(f"summary: {len(results) - len(failed)} passed, {len(failed)} failed")

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
