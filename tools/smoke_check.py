#!/usr/bin/env python3
"""Smoke-check one generated Avereth host bundle."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Sequence

from agent_bundle_check import DEFAULT_MANIFEST, validate_agent_bundle
from host_leak_check import validate_host_bundle
from legacy_runtime_retirement import (
    contains_legacy_identity,
    identity_allowed,
    prompt_forbidden_tokens,
    retired_repository_relatives,
    retired_top_levels,
)
from runtime_parity import forbidden_runtime_files


REQUIRED_SKILLS = {
    "aers-prisma-slr", "aers-thematic-analysis", "cnki-advanced-search",
    "cnki-download", "cnki-export", "cnki-journal-index", "cnki-journal-search",
    "cnki-journal-toc", "cnki-navigate-pages", "cnki-paper", "cnki-paper-detail",
    "cnki-parse-results", "cnki-search", "cnki-snowball", "empirical-research",
    "intl-export", "intl-search", "journal-fit", "page-evidence",
    "qual-content-analysis", "qual-process-tracing", "qual-qca",
    "quant-causal-inference", "text-as-data-cn",
}
REQUIRED_RUNTIME = (
    "skills/cnki-paper/SKILL.md",
    "skills/cnki-paper/host_profile.json",
    "skills/cnki-paper/scripts/avereth.py",
    "skills/cnki-paper/scripts/codex_cnki_gate.py",
    "skills/cnki-paper/scripts/topic_packet.py",
    "skills/cnki-paper/scripts/research_decision.py",
    "skills/cnki-paper/scripts/avereth_core/cli.py",
    "skills/cnki-paper/scripts/avereth_core/config.py",
    "skills/cnki-paper/scripts/avereth_core/stages.py",
    "skills/cnki-paper/scripts/avereth_core/hosts/base.py",
    "skills/cnki-paper/scripts/avereth_core/hosts/codex.py",
    "skills/cnki-paper/scripts/avereth_core/hosts/claude.py",
    "skills/cnki-paper/scripts/avereth_core/hosts/agent_declared.py",
    "skills/cnki-paper/scripts/avereth_core/hosts/profile.py",
    "skills/cnki-paper/scripts/avereth_core/audit/run_all.py",
    "skills/cnki-paper/scripts/avereth_core/build/run.py",
    "skills/cnki-paper/scripts/avereth_core/build/manuscript_compiler.py",
    "skills/cnki-paper/scripts/avereth_core/output/run.py",
    "skills/cnki-paper/scripts/avereth_core/output/translation.py",
    "skills/cnki-paper/scripts/avereth_core/output/submission.py",
    "skills/cnki-paper/scripts/avereth_core/output/response.py",
    "skills/cnki-paper/scripts/avereth_core/output/word_render.ps1",
    "skills/cnki-paper/scripts/avereth_core/legacy/workspace_migration.py",
    "skills/cnki-paper/scripts/avereth_core/tools/_engine_utils.py",
    "skills/cnki-paper/references/host-runtime.md",
    "skills/cnki-paper/references/schemas/avereth-workflow-config-v1.schema.json",
    "skills/cnki-paper/references/engine/manuscript-compiler.md",
    "skills/cnki-paper/references/manuscript-profiles/empirical-social-science-v1.json",
    "skills/cnki-paper/references/schemas/avereth-manuscript-contract-v1.schema.json",
    "skills/cnki-paper/references/schemas/avereth-manuscript-ir-v1.schema.json",
    "skills/cnki-paper/references/schemas/avereth-manuscript-rebuild-proof-v1.schema.json",
    "skills/empirical-research/references/researcher-collaboration.md",
    "skills/empirical-research/scripts/researcher_dispatch.py",
    "host_profile.json",
    "build-manifest.json",
)
EXPECTED_RUNNERS = {
    "codex": ("codex-exec", ("codex-exec",)),
    "claude": ("claude-exec", ("claude-exec", "agent-declared")),
}


def smoke_check(
    root: Path,
    host: str,
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
) -> tuple[list[str], list[str]]:
    root = root.resolve()
    skills = root / "skills"
    errors: list[str] = []
    warnings: list[str] = []

    def err(message: str) -> None:
        errors.append(message)

    def text(relative: str) -> str:
        try:
            return (root / relative).read_text(encoding="utf-8-sig")
        except OSError:
            return ""

    if not root.is_dir():
        return [f"bundle root is missing: {root}"], warnings
    actual_skills = {path.name for path in skills.iterdir() if path.is_dir()} if skills.is_dir() else set()
    for name in sorted(REQUIRED_SKILLS - actual_skills):
        err(f"required skill missing: {name}")
    for name in retired_top_levels(skills):
        err(f"retired top-level skill remains: {name}")

    names: set[str] = set()
    if skills.is_dir():
        for directory in sorted((path for path in skills.iterdir() if path.is_dir()), key=lambda path: path.name):
            skill_file = directory / "SKILL.md"
            metadata_file = directory / "agents" / "openai.yaml"
            if not skill_file.is_file():
                err(f"{directory.name}: missing SKILL.md")
                continue
            content = skill_file.read_text(encoding="utf-8-sig")
            front = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
            if not front:
                err(f"{directory.name}: invalid SKILL.md frontmatter")
                continue
            name_match = re.search(r"^name:\s*(\S+)", front.group(1), re.MULTILINE)
            description = re.search(r"^description:\s*(.+)", front.group(1), re.MULTILINE)
            if not name_match or name_match.group(1) != directory.name:
                err(f"{directory.name}: frontmatter name mismatch")
            elif directory.name in names:
                err(f"{directory.name}: duplicate skill name")
            else:
                names.add(directory.name)
            if not description or len(description.group(1).strip()) < 20:
                err(f"{directory.name}: description missing or too short")
            if host == "codex" and not metadata_file.is_file():
                err(f"{directory.name}: missing agents/openai.yaml")
            if host == "claude" and metadata_file.exists():
                err(f"{directory.name}: OpenAI-only metadata leaked into Claude bundle")

    for relative in REQUIRED_RUNTIME:
        if not (root / relative).is_file():
            err(f"required runtime file missing: {relative}")
    entrypoint = "prompts/avereth.md" if host == "codex" else "commands/avereth.md"
    if not (root / entrypoint).is_file():
        err(f"required runtime file missing: {entrypoint}")

    for relative in retired_repository_relatives():
        if (root / relative).exists():
            err(f"retired runtime file remains: {relative}")

    prompt = text(entrypoint)
    invocation = "$cnki-paper" if host == "codex" else "`cnki-paper`"
    if invocation not in prompt or "cnki-paper/SKILL.md" not in prompt:
        err(f"{host} entrypoint must route through the installed cnki-paper Skill")
    for forbidden in prompt_forbidden_tokens():
        if forbidden in prompt:
            err(f"Avereth entrypoint contains retired instruction: {forbidden}")

    skill = text("skills/cnki-paper/SKILL.md")
    if "avereth.py" not in skill:
        err("cnki-paper Skill must provide the controller bootstrap")
    version_source = text("skills/cnki-paper/scripts/avereth_core/version.py")
    version_match = re.search(r'^VERSION\s*=\s*"([^"]+)"', version_source, re.MULTILINE)
    version = version_match.group(1) if version_match else ""
    if not version or f"v{version}" not in skill:
        err("engine and SKILL versions are not synchronized")

    try:
        profile = json.loads(text("host_profile.json"))
    except json.JSONDecodeError:
        err("runtime host profile is not JSON")
    else:
        default_runner, allowed_runners = EXPECTED_RUNNERS[host]
        if profile.get("host_id") != host:
            err("runtime host profile identity mismatch")
        if profile.get("default_runner") != default_runner:
            err("runtime host profile default runner mismatch")
        if tuple(profile.get("allowed_runners") or ()) != allowed_runners:
            err("runtime host profile allowed runners mismatch")

    for message in validate_agent_bundle(
        root / "agents", host=host, manifest_path=manifest_path
    ):
        err(f"agent bundle: {message}")
    for message in validate_host_bundle(root, host):
        err(f"host bundle: {message}")

    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {
            ".py", ".md", ".toml", ".yaml", ".yml", ".json", ".ps1", ".sh"
        }:
            continue
        relative_path = path.relative_to(root)
        if any(part in {"__pycache__", ".pytest_cache", "node_modules"} for part in relative_path.parts):
            continue
        relative = relative_path.as_posix()
        if relative == "build-manifest.json":
            continue
        if identity_allowed(relative):
            continue
        content = path.read_text(encoding="utf-8-sig", errors="replace")
        if contains_legacy_identity(content):
            err(f"live legacy identity remains outside the migration allowlist: {relative}")

    forbidden_runtime = forbidden_runtime_files(skills, top_levels=actual_skills)
    for relative in forbidden_runtime:
        err(f"repository-only file shipped in bundle: {relative}")

    bare_python_command = re.compile(
        r"(?m)(?<!Get-Command )\bpython(?:\.exe)?[ \t]+(?=[&$<./\\A-Za-z_-])"
    )
    documentation_roots = (
        skills / "cnki-paper" / "SKILL.md",
        skills / "cnki-paper" / "references",
    )
    for document_root in documentation_roots:
        candidates = [document_root] if document_root.is_file() else list(document_root.rglob("*.md"))
        for path in candidates:
            content = path.read_text(encoding="utf-8-sig", errors="replace")
            if bare_python_command.search(content):
                err(
                    "workflow documentation must use the bootstrapped $Python runtime: "
                    + path.relative_to(root).as_posix()
                )

    controller = root / "skills" / "cnki-paper" / "scripts" / "avereth.py"
    for arguments, label in (
        (["--help"], "CLI help"),
        (["manuscript", "--help"], "manuscript CLI help"),
        (["manuscript", "restore-legacy", "--help"], "manuscript restore CLI help"),
        (["--skills-dir", str(skills), "doctor", "--json"], "global doctor"),
    ):
        if not controller.is_file():
            break
        result = subprocess.run(
            [sys.executable, "-X", "utf8", str(controller), *arguments],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        if result.returncode != 0:
            err(f"{label} failed: {' '.join((result.stdout + result.stderr).split())[-500:]}")
        elif label == "global doctor":
            try:
                payload = json.loads(result.stdout)
            except json.JSONDecodeError:
                err("global doctor did not return JSON")
            else:
                if payload.get("status") != "PASS" or payload.get("state_model") != "eight-stage-local":
                    err("global doctor did not confirm the v7 local eight-stage engine")
    return errors, warnings


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--host", choices=tuple(EXPECTED_RUNNERS), required=True)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args(argv)
    errors, warnings = smoke_check(
        args.bundle, args.host, manifest_path=args.manifest
    )
    print(f"# Avereth {args.host} Bundle Smoke Check")
    print()
    print(f"Status: {'PASS' if not errors else 'FAIL'}")
    print(f"- errors: {len(errors)}")
    print(f"- warnings: {len(warnings)}")
    for message in errors:
        print(f"  - ERROR: {message}")
    for message in warnings:
        print(f"  - WARNING: {message}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
