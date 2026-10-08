#!/usr/bin/env python3
"""Validate the typed workflow registry and its generated documentation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "cnki-paper" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from avereth_core.workflow_registry import (  # noqa: E402
    ARTIFACT_DEFINITIONS,
    GLOBAL_RUNTIME_FILES,
    PROFILE_REFERENCE_PATHS,
    STAGE_DEFINITIONS,
    TASK_PROFILE_TERMINALS,
    migration_schema_allowlist,
    registry_issues,
    stage_artifact_definitions,
)


DOC_PATH = ROOT / "docs" / "WORKFLOW_REGISTRY.md"


def render() -> str:
    terminal_by_stage: dict[str, list[str]] = {}
    for profile, terminal in TASK_PROFILE_TERMINALS.items():
        terminal_by_stage.setdefault(terminal, []).append(profile)
    lines = [
        "# Workflow Registry (generated)",
        "",
        "This file is generated from `avereth_core/workflow_registry.py`. Do not edit its tables by hand.",
        "",
        "## Public stages",
        "",
        "| Stage | Required base artifacts | Terminal profiles |",
        "|---|---:|---|",
    ]
    for stage in STAGE_DEFINITIONS:
        terminals = ", ".join(sorted(terminal_by_stage.get(stage.key, []))) or "—"
        lines.append(f"| {stage.key} | {len(stage_artifact_definitions(stage.key))} | {terminals} |")
    lines.extend(
        [
            "",
            "## Contract projections",
            "",
            f"- Artifact definitions: {len(ARTIFACT_DEFINITIONS)}",
            f"- Global doctor runtime files: {len(GLOBAL_RUNTIME_FILES)}",
            f"- Schema-bearing migration contracts: {len(migration_schema_allowlist())}",
            "",
            "## Schema allow-list",
            "",
            "| Artifact | Accepted schemas during migration |",
            "|---|---|",
        ]
    )
    for path, schemas in sorted(migration_schema_allowlist().items(), key=lambda item: item[0].as_posix()):
        lines.append(f"| `{path.as_posix()}` | {', '.join(sorted(schemas))} |")
    lines.append("")
    return "\n".join(lines)


def check() -> list[str]:
    issues = list(registry_issues())
    skills_dir = ROOT / "skills"
    for relative in GLOBAL_RUNTIME_FILES:
        candidate = skills_dir / relative
        if relative == "cnki-paper/SKILL.md":
            candidate = skills_dir / "cnki-paper/SKILL.source.md"
        if not candidate.is_file():
            issues.append(f"missing registered runtime file: {relative}")
    for stage in STAGE_DEFINITIONS:
        for relative in stage.references:
            if not (skills_dir / relative).is_file():
                issues.append(f"missing stage reference ({stage.key}): {relative}")
    for profile, references in PROFILE_REFERENCE_PATHS.items():
        for relative in references:
            if not (skills_dir / relative).is_file():
                issues.append(f"missing profile reference ({profile}): {relative}")
    expected = render()
    try:
        actual = DOC_PATH.read_text(encoding="utf-8")
    except OSError:
        issues.append(f"missing generated registry document: {DOC_PATH.relative_to(ROOT).as_posix()}")
    else:
        if actual != expected:
            issues.append("docs/WORKFLOW_REGISTRY.md is stale; run check_workflow_registry.py --write")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.write:
        DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
        DOC_PATH.write_text(render(), encoding="utf-8")
        print(f"wrote {DOC_PATH.relative_to(ROOT).as_posix()}")
        return 0
    issues = check()
    if issues:
        print("Workflow registry check: FAIL")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("Workflow registry check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
