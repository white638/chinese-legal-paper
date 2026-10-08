#!/usr/bin/env python3
"""Recoverably retire legacy and replaced paths from a host runtime.

This migration-only module is the single repository location that knows the
retired product names. Installers, parity checks, and smoke tests consume its
neutral API instead of carrying legacy worker-cleanup logic themselves.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path


_RETIRED_TOP_LEVELS = (
    "paper-spine",
    "paper-spine-audit",
    "paper-spine-build",
    "paper-spine-citation",
    "paper-spine-humanize",
    "paper-spine-intake",
    "paper-spine-latex",
    "paper-spine-research",
    "paper-spine-rewrite",
    "paper-spine-translate",
    "paper-spine-ui",
    "paper-spine-update",
)
_RETIRED_PROMPT = "paperspine.md"
_RETIRED_AGENTS = (
    "cnki-researcher.md",
    "cnki-researcher.toml",
    "cnki-paper-director.toml",
    "cnki-methods-reviewer.toml",
    "cnki-contribution-reviewer.toml",
    "cnki-clarity-reviewer.toml",
)
_MANAGED_AGENT_BASES = (
    "avereth",
    "avereth_methods",
    "avereth_contribution",
    "avereth_clarity",
    "avereth_writer",
    "avereth_compressor",
    "avereth_researcher",
    "avereth_adjudicator",
    "avereth_scout",
)
_HOST_LAYOUTS = {
    "codex": {"entrypoint_dir": "prompts", "agent_extension": ".toml"},
    "claude": {"entrypoint_dir": "commands", "agent_extension": ".md"},
}
_RETIRED_REPOSITORY_RELATIVES = (
    "prompts/paperspine.md",
    "skills/cnki-paper/scripts/apply_cnki_patches.py",
    "skills/cnki-paper/scripts/avereth_core/tools/progress_check.py",
    "skills/cnki-paper/scripts/avereth_core/tools/paperspine_update.py",
    "skills/cnki-paper/scripts/avereth_core/tools/launch_paperspine_ui.ps1",
    "skills/cnki-paper/scripts/avereth_core/tools/launch_paperspine_ui.sh",
)
_PROMPT_FORBIDDEN = ("$paper-spine", "launch_paperspine_ui", "paper_spine_config.json")
_IDENTITY = re.compile(r"PaperSpine|paper-spine|paper_spine", re.IGNORECASE)
_SOURCE_NOTICE_PATHS = (
    "licenses/PaperSpine-MIT.txt",
    "THIRD_PARTY_NOTICES.md",
    "docs/UPSTREAM.md",
)
_LEGACY_ALLOW = {
    "CHANGELOG.md",
    *_SOURCE_NOTICE_PATHS,
    "skills/cnki-paper/scripts/avereth_core/config.py",
    "skills/cnki-paper/scripts/avereth_core/receipts.py",
    "skills/cnki-paper/scripts/avereth_core/legacy/workspace_migration.py",
    "tools/legacy_runtime_retirement.py",
}


def retired_top_levels(root: Path) -> list[str]:
    return sorted(name for name in _RETIRED_TOP_LEVELS if (root / name).exists())


def retired_repository_relatives() -> tuple[str, ...]:
    return _RETIRED_REPOSITORY_RELATIVES


def retired_agent_names() -> tuple[str, ...]:
    return _RETIRED_AGENTS


def managed_agent_names(host: str = "codex") -> tuple[str, ...]:
    try:
        extension = str(_HOST_LAYOUTS[host]["agent_extension"])
    except KeyError as exc:
        raise ValueError(f"unsupported host: {host!r}") from exc
    return tuple(name + extension for name in _MANAGED_AGENT_BASES)


def prompt_forbidden_tokens() -> tuple[str, ...]:
    return _PROMPT_FORBIDDEN


def source_notice_paths() -> tuple[str, ...]:
    return _SOURCE_NOTICE_PATHS


def identity_allowed(relative: str) -> bool:
    return relative in _LEGACY_ALLOW or relative.startswith(
        "skills/cnki-paper/scripts/avereth_core/legacy/"
    )


def contains_legacy_identity(content: str) -> bool:
    return bool(_IDENTITY.search(content))


def _move_exact_file(
    source: Path,
    expected_parent: Path,
    expected_name: str,
    destination: Path,
    moved: list[dict[str, str]],
) -> None:
    if not source.exists():
        return
    if source.parent != expected_parent or source.name != expected_name or not source.is_file():
        raise RuntimeError(f"refusing to retire or replace an unexpected file path: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise RuntimeError(f"retirement backup already exists: {destination}")
    shutil.move(str(source), str(destination))
    moved.append({"source": str(source), "backup": str(destination)})


def retire(runtime_home: Path, backup_root: Path, host: str = "codex") -> dict[str, object]:
    if host not in _HOST_LAYOUTS:
        raise ValueError(f"unsupported host: {host!r}")
    runtime_home = runtime_home.resolve()
    skills = (runtime_home / "skills").resolve()
    agents = (runtime_home / "agents").resolve()
    entrypoint_dir_name = str(_HOST_LAYOUTS[host]["entrypoint_dir"])
    entrypoints = (runtime_home / entrypoint_dir_name).resolve()
    backup_root = backup_root.resolve()
    backup_root.mkdir(parents=True, exist_ok=True)
    moved: list[dict[str, str]] = []

    for name in _RETIRED_TOP_LEVELS:
        source = (skills / name).resolve()
        if not source.exists():
            continue
        if source.parent != skills or source.name != name:
            raise RuntimeError(f"refusing to retire an unexpected skill path: {source}")
        destination = backup_root / "retired-skills" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise RuntimeError(f"retirement backup already exists: {destination}")
        shutil.move(str(source), str(destination))
        moved.append({"source": str(source), "backup": str(destination)})

    _move_exact_file(
        (entrypoints / _RETIRED_PROMPT).resolve(),
        entrypoints,
        _RETIRED_PROMPT,
        backup_root / f"retired-{entrypoint_dir_name}" / _RETIRED_PROMPT,
        moved,
    )
    for name in _RETIRED_AGENTS:
        _move_exact_file(
            (agents / name).resolve(),
            agents,
            name,
            backup_root / "retired-agents" / name,
            moved,
        )
    for name in managed_agent_names(host):
        _move_exact_file(
            (agents / name).resolve(),
            agents,
            name,
            backup_root / "replaced-agents" / name,
            moved,
        )
    for name in ("avereth.md",):
        _move_exact_file(
            (entrypoints / name).resolve(),
            entrypoints,
            name,
            backup_root / f"replaced-{entrypoint_dir_name}" / name,
            moved,
        )
    return {
        "status": "PASS",
        "host": host,
        "moved": moved,
        "backup_root": str(backup_root),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    homes = parser.add_mutually_exclusive_group(required=True)
    homes.add_argument("--runtime-home", type=Path)
    homes.add_argument("--codex-home", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--host", choices=tuple(_HOST_LAYOUTS), default="codex")
    parser.add_argument("--backup-root", required=True, type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    runtime_home = args.runtime_home or args.codex_home
    payload = retire(runtime_home, args.backup_root, args.host)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Status: {payload['status']}")
        print(f"Moved: {len(payload['moved'])}")
        print(f"Backup: {payload['backup_root']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
