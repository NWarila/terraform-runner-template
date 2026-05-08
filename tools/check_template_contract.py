#!/usr/bin/env python3
"""Verify that a consumer repository conforms to the golden template contract.

The contract is defined in `contract/golden-template-contract.yaml`. This
script walks the repository under inspection and emits one PASS/FAIL line per
rule, exiting non-zero if any rule fails.

The contract has two layers:
  - Universal requirements (apply to every consumer regardless of type).
  - Type-specific requirements: `framework` (self-contained module) or
    `runner` (data-only deployer that consumes a framework at runtime).

Repo type is determined in this order:
  1. --type CLI flag.
  2. `.template-type` file in the repo root containing "framework" or "runner".
  3. Inference: terraform/versions.tf present -> framework; repos/public/ or
     repos/private/ present -> runner.

If neither flag, file, nor inference resolves a type, the validator errors
loudly. Type ambiguity is a contract failure.

Usage:
    check_template_contract.py [--repo-root PATH] [--contract PATH]
                               [--template-root PATH] [--type framework|runner]
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.stderr.write(
        "error: PyYAML is required. Install with `pip install pyyaml`.\n"
    )
    sys.exit(2)


SHA_RE = re.compile(r"^[0-9a-f]{40}$")
USES_LINE_RE = re.compile(r"^\s*uses:\s*([^\s#]+)")
REQUIRED_VERSION_RE = re.compile(
    r'^\s*required_version\s*=\s*"=\s*[0-9]+\.[0-9]+\.[0-9]+"\s*(?:#.*|//.*)?$',
    re.MULTILINE,
)
EXACT_PROVIDER_VERSION_RE = re.compile(r"^=\s*[0-9]+\.[0-9]+\.[0-9]+$")
PROVIDER_START_RE = re.compile(r"^\s*([A-Za-z0-9_-]+)\s*=\s*\{")
VERSION_ATTR_RE = re.compile(r'^\s*version\s*=\s*"([^"]+)"\s*(?:#.*|//.*)?$')

VALID_TYPES = ("framework", "runner")


@dataclass
class RuleResult:
    name: str
    passed: bool
    detail: str = ""


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


def strip_block_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)


def check_terraform_version_pins(repo_root: Path) -> list[RuleResult]:
    target = repo_root / "terraform" / "versions.tf"
    if not target.is_file():
        return [
            RuleResult(
                name="terraform_required_version_exact",
                passed=False,
                detail="terraform/versions.tf not found",
            ),
            RuleResult(
                name="terraform_provider_pinning",
                passed=False,
                detail="terraform/versions.tf not found",
            ),
        ]

    text = strip_block_comments(target.read_text(encoding="utf-8"))
    results: list[RuleResult] = []
    results.append(
        RuleResult(
            name="terraform_required_version_exact",
            passed=REQUIRED_VERSION_RE.search(text) is not None,
            detail=""
            if REQUIRED_VERSION_RE.search(text)
            else 'required_version must be an uncommented exact `= X.Y.Z` line',
        )
    )

    block = extract_required_providers_block(text)
    if block is None:
        results.append(
            RuleResult(
                name="terraform_provider_pinning",
                passed=True,
                detail="no required_providers block",
            )
        )
        return results

    provider_results = check_provider_blocks(block)
    if provider_results:
        results.extend(provider_results)
    else:
        results.append(RuleResult(name="terraform_provider_pinning", passed=True))
    return results


def extract_required_providers_block(text: str) -> str | None:
    match = re.search(r"\brequired_providers\s*\{", text)
    if not match:
        return None
    start = text.find("{", match.start())
    depth = 0
    for idx in range(start, len(text)):
        char = text[idx]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : idx]
    return text[start + 1 :]


def check_provider_blocks(block: str) -> list[RuleResult]:
    results: list[RuleResult] = []
    lines = block.splitlines()
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        start = PROVIDER_START_RE.match(line)
        if not start:
            idx += 1
            continue
        provider = start.group(1)
        start_line = idx + 1
        depth = line.count("{") - line.count("}")
        body = [line]
        idx += 1
        while idx < len(lines) and depth > 0:
            body.append(lines[idx])
            depth += lines[idx].count("{") - lines[idx].count("}")
            idx += 1
        version_values: list[tuple[int, str]] = []
        for offset, body_line in enumerate(body, start_line):
            version = VERSION_ATTR_RE.match(body_line)
            if version:
                version_values.append((offset, version.group(1).strip()))
        if not version_values:
            results.append(
                RuleResult(
                    name=f"terraform_provider_pinning:{provider}",
                    passed=False,
                    detail="provider is missing an exact version pin",
                )
            )
            continue
        for line_no, value in version_values:
            results.append(
                RuleResult(
                    name=f"terraform_provider_pinning:{provider}",
                    passed=EXACT_PROVIDER_VERSION_RE.match(value) is not None,
                    detail=""
                    if EXACT_PROVIDER_VERSION_RE.match(value)
                    else f"line {line_no}: version must be `= X.Y.Z` (got `{value}`)",
                )
            )
    return results


def check_gitignore_wildcards(repo_root: Path) -> RuleResult:
    target = repo_root / ".gitignore"
    if not target.is_file():
        return RuleResult(
            name="gitignore:wildcards",
            passed=False,
            detail=".gitignore not found",
        )
    offenders: list[str] = []
    for lineno, line in enumerate(target.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "*" in stripped and stripped != "**":
            offenders.append(f"{lineno}:{stripped}")
    return RuleResult(
        name="gitignore:wildcards",
        passed=not offenders,
        detail="" if not offenders else "wildcards other than leading `**`: " + ", ".join(offenders),
    )


def check_sync_drift(
    repo_root: Path, template_root: Path, manifest: Path
) -> list[RuleResult]:
    """Verify that synced files in the consumer match the template byte-for-byte."""
    if not manifest.is_file():
        return [
            RuleResult(
                name="sync_drift",
                passed=False,
                detail=f"sync manifest not found at {manifest}",
            )
        ]
    spec = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    results: list[RuleResult] = []
    for entry in spec.get("synced_files", []):
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


def detect_repo_type(repo_root: Path, cli_type: str | None) -> tuple[str | None, str]:
    """Return (repo_type, source_description). repo_type is None on failure."""
    if cli_type:
        if cli_type not in VALID_TYPES:
            return None, f"--type {cli_type!r} is not one of {VALID_TYPES}"
        return cli_type, "--type CLI flag"

    type_file = repo_root / ".template-type"
    if type_file.is_file():
        declared = type_file.read_text(encoding="utf-8").strip()
        if declared not in VALID_TYPES:
            return None, f".template-type contains {declared!r} (expected one of {VALID_TYPES})"
        return declared, ".template-type file"

    has_terraform = (repo_root / "terraform" / "versions.tf").is_file()
    has_runner_dirs = (repo_root / "repos" / "public").is_dir() or (
        repo_root / "repos" / "private"
    ).is_dir()
    if has_terraform and has_runner_dirs:
        return None, "ambiguous: both terraform/versions.tf and repos/* present"
    if has_terraform:
        return "framework", "inferred from terraform/versions.tf"
    if has_runner_dirs:
        return "runner", "inferred from repos/public|private"
    return None, "no terraform/versions.tf and no repos/* — cannot infer"


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
        / "golden-template-contract.yaml",
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
        choices=VALID_TYPES,
        default=None,
        help=(
            "Override repo type detection. By default the validator reads "
            ".template-type or infers from repo layout."
        ),
    )
    args = parser.parse_args()

    if not args.contract.is_file():
        sys.stderr.write(f"error: contract not found at {args.contract}\n")
        return 2

    contract = yaml.safe_load(args.contract.read_text(encoding="utf-8"))
    repo_root = args.repo_root.resolve()

    repo_type, source = detect_repo_type(repo_root, args.type)
    if repo_type is None:
        sys.stderr.write(f"error: cannot determine repo type ({source}).\n")
        sys.stderr.write(
            "  pass --type framework or --type runner, or create a "
            ".template-type file with one of those values.\n"
        )
        return 2
    print(f"repo type: {repo_type} ({source})")
    print()

    universal = contract.get("universal", {})
    type_block = (contract.get("types") or {}).get(repo_type, {})

    results: list[RuleResult] = []

    for entry in universal.get("required_root_files", []):
        results.append(check_path(repo_root, entry))
    for entry in universal.get("required_github_files", []):
        results.append(check_path(repo_root, entry))
    for entry in universal.get("required_documentation", []):
        results.append(check_path(repo_root, entry))

    for entry in type_block.get("required_paths", []):
        results.append(check_path(repo_root, entry))
    for rule in type_block.get("content_rules", []):
        results.append(check_content_rule(repo_root, rule))

    if repo_type == "framework":
        results.extend(check_terraform_version_pins(repo_root))

    results.append(check_gitignore_wildcards(repo_root))

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
