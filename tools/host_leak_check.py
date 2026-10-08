#!/usr/bin/env python3
"""Detect unresolved templates and operational cross-host leakage in a built bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Sequence


HOSTS = ("codex", "claude")
PUBLIC_SUFFIXES = {".md", ".toml", ".yaml", ".yml", ".txt"}
UNRESOLVED_TOKEN = re.compile(r"\{\{[A-Z][A-Z0-9_]*\}\}")
FORBIDDEN = {
    "codex": (
        "CLAUDE_CONFIG_DIR",
        "CLAUDE_PYTHON",
        "$ClaudeHome",
        "~/.claude/skills",
        ".claude\\skills",
        "ClaudeExec",
        "claude-subskill-adapter.md",
        "claude-method-adapter.md",
        "mcp__chrome-devtools__",
    ),
    "claude": (
        "CODEX_HOME",
        "CODEX_PYTHON",
        "$CodexHome",
        "~/.codex/skills",
        ".codex\\skills",
        "codex-runtimes",
        "CodexExec",
        "codex-subskill-adapter.md",
        "codex-method-adapter.md",
        "chrome:control-chrome",
        "## Codex 集成",
    ),
}
PUBLIC_ALLOWLIST = {
    "codex": {"skills/journal-fit/packs/PROVENANCE.md"},
    "claude": set(),
}
SOURCE_FORBIDDEN = (
    "CODEX_HOME",
    "CODEX_PYTHON",
    "CLAUDE_CONFIG_DIR",
    "CLAUDE_PYTHON",
    "~/.codex",
    "~/.claude",
    ".codex\\skills",
    ".claude\\skills",
    "CodexExec",
    "ClaudeExec",
    "chrome:control-chrome",
    "mcp__chrome-devtools__",
    "codex-subskill-adapter.md",
    "claude-subskill-adapter.md",
    "codex-method-adapter.md",
    "claude-method-adapter.md",
    "## Codex 集成",
)
SOURCE_ALLOWLIST = {"skills/journal-fit/packs/PROVENANCE.md"}


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return payload


def _digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def _public_files(bundle: Path, host: str) -> list[Path]:
    roots = [bundle / "skills", bundle / "agents"]
    roots.append(bundle / ("prompts" if host == "codex" else "commands"))
    files: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        files.extend(
            path
            for path in root.rglob("*")
            if path.is_file() and path.suffix.lower() in PUBLIC_SUFFIXES
        )
    return sorted(files, key=lambda item: item.as_posix())


def validate_manifest(bundle: Path, host: str) -> list[str]:
    errors: list[str] = []
    path = bundle / "build-manifest.json"
    try:
        manifest = _read_json(path)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        return [f"build manifest is invalid: {exc}"]
    if manifest.get("schema_version") != "avereth-host-build-manifest/v1":
        errors.append("build manifest schema mismatch")
    if manifest.get("host_id") != host:
        errors.append("build manifest host mismatch")
    declared = manifest.get("files")
    if not isinstance(declared, dict):
        return errors + ["build manifest files must be an object"]
    actual = {
        path.relative_to(bundle).as_posix(): _digest(path)
        for path in sorted(bundle.rglob("*"), key=lambda item: item.as_posix())
        if path.is_file() and path.name != "build-manifest.json"
    }
    if set(declared) != set(actual):
        missing = sorted(set(declared) - set(actual))
        extra = sorted(set(actual) - set(declared))
        if missing:
            errors.append("manifest paths missing from bundle: " + ", ".join(missing[:5]))
        if extra:
            errors.append("bundle paths missing from manifest: " + ", ".join(extra[:5]))
    for relative in sorted(set(declared) & set(actual)):
        if declared[relative] != actual[relative]:
            errors.append(f"build manifest hash mismatch: {relative}")
    if manifest.get("file_count") != len(actual):
        errors.append("build manifest file_count mismatch")
    return errors


def validate_host_bundle(bundle: Path, host: str) -> list[str]:
    errors: list[str] = []
    bundle = bundle.resolve()
    if host not in HOSTS:
        return [f"unsupported host: {host!r}"]
    if not bundle.is_dir():
        return [f"bundle directory is missing: {bundle}"]
    try:
        profile = _read_json(bundle / "host_profile.json")
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"runtime host profile is invalid: {exc}")
    else:
        if profile.get("schema_version") != "avereth-host-profile/v1":
            errors.append("runtime host profile schema mismatch")
        if profile.get("host_id") != host:
            errors.append("runtime host profile identity mismatch")

    expected_entry = bundle / ("prompts" if host == "codex" else "commands") / "avereth.md"
    forbidden_entry = bundle / ("commands" if host == "codex" else "prompts") / "avereth.md"
    if not expected_entry.is_file():
        errors.append(f"{host} entrypoint is missing: {expected_entry.relative_to(bundle)}")
    if forbidden_entry.exists():
        errors.append(f"opposite-host entrypoint leaked: {forbidden_entry.relative_to(bundle)}")

    metadata = list((bundle / "skills").rglob("openai.yaml"))
    if host == "codex" and not metadata:
        errors.append("Codex bundle lacks OpenAI skill metadata")
    if host == "claude" and metadata:
        errors.append("Claude bundle contains OpenAI-only skill metadata")

    for path in _public_files(bundle, host):
        relative = path.relative_to(bundle).as_posix()
        content = path.read_text(encoding="utf-8-sig", errors="replace")
        token = UNRESOLVED_TOKEN.search(content)
        if token:
            errors.append(f"unresolved template token {token.group(0)!r}: {relative}")
        if relative in PUBLIC_ALLOWLIST[host]:
            continue
        for forbidden in FORBIDDEN[host]:
            if forbidden in content:
                errors.append(f"{host} public file contains {forbidden!r}: {relative}")

    errors.extend(validate_manifest(bundle, host))
    return errors


def validate_source_tree(root: Path) -> list[str]:
    """Require host-neutral public source templates before rendering."""

    root = root.resolve()
    errors: list[str] = []
    source_roots = (root / "skills", root / "agent-specs", root / "entrypoints")
    for source_root in source_roots:
        if not source_root.is_dir():
            errors.append(f"canonical source root is missing: {source_root.relative_to(root)}")
            continue
        for path in sorted(source_root.rglob("*"), key=lambda item: item.as_posix()):
            if not path.is_file() or path.suffix.lower() not in PUBLIC_SUFFIXES:
                continue
            relative = path.relative_to(root).as_posix()
            if relative in SOURCE_ALLOWLIST:
                continue
            content = path.read_text(encoding="utf-8-sig", errors="replace")
            for forbidden in SOURCE_FORBIDDEN:
                if forbidden in content:
                    errors.append(
                        f"canonical public source contains host literal {forbidden!r}: {relative}"
                    )
    return errors


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--host", choices=HOSTS)
    parser.add_argument("--source", action="store_true")
    args = parser.parse_args(argv)
    if args.source:
        if args.host:
            parser.error("--source and --host are mutually exclusive")
        errors = validate_source_tree(args.root)
        label = "canonical source"
    else:
        if not args.host:
            parser.error("--host is required for a generated bundle")
        errors = validate_host_bundle(args.root, args.host)
        label = f"{args.host} bundle"
    for message in errors:
        print(f"ERROR {message}")
    if errors:
        print(f"FAIL: {len(errors)} host bundle error(s)")
        return 1
    print(f"PASS: {label} has no operational cross-host leakage")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
