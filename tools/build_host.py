#!/usr/bin/env python3
"""Build one host-specific Avereth bundle from the canonical source tree."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence


BUILD_PROFILE_SCHEMA = "avereth-host-build-profile/v1"
RUNTIME_PROFILE_SCHEMA = "avereth-host-profile/v1"
MANIFEST_SCHEMA = "avereth-host-build-manifest/v1"
HOSTS = ("codex", "claude")
TEXT_SUFFIXES = {".md", ".txt"}
IGNORED_NAMES = {"__pycache__", ".pytest_cache", ".ruff_cache", "node_modules"}
_TEMPLATE_TOKEN = re.compile(r"\{\{([A-Z0-9_]+)\}\}")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return payload


def load_profile(repo_root: Path, host: str) -> dict[str, Any]:
    if host not in HOSTS:
        raise ValueError(f"unsupported host: {host!r}")
    profile_path = repo_root / "hosts" / host / "profile.json"
    profile = _read_json(profile_path)
    if profile.get("schema_version") != BUILD_PROFILE_SCHEMA:
        raise ValueError(f"invalid build profile schema: {profile_path}")
    if profile.get("host_id") != host:
        raise ValueError(f"host profile identity mismatch: {profile_path}")
    allowed = profile.get("allowed_runners")
    if not isinstance(allowed, list) or profile.get("default_runner") not in allowed:
        raise ValueError(f"invalid runner capability matrix: {profile_path}")
    discovery = profile.get("discovery_channel")
    expected = {"mode": "primary_search_broker", "allowed_tools": ["exa.search", "web.search"],
                "direct_agent_tools": False, "context": "fresh_no_parent_history"}
    if discovery != expected:
        raise ValueError(f"invalid public discovery channel: {profile_path}")
    return profile


def _load_tokens(repo_root: Path, profile: Mapping[str, Any]) -> dict[str, str]:
    tokens = {
        str(key): str(value)
        for key, value in (profile.get("template_tokens") or {}).items()
    }
    tokens["SKILL_INVOCATION"] = str(profile["skill_invocation"])
    host_dir = repo_root / "hosts" / str(profile["host_id"])
    for key, relative in (profile.get("template_fragments") or {}).items():
        path = host_dir / str(relative)
        if not path.is_file():
            raise ValueError(f"missing host template fragment: {path}")
        fragment = path.read_text(encoding="utf-8-sig")
        # Markdown fragments are standalone blocks.  Plain-text fragments are
        # inline clauses and must not inject their file-final newline into the
        # surrounding sentence.
        if path.suffix.casefold() == ".txt":
            fragment = fragment.rstrip("\r\n")
        tokens[str(key)] = fragment
    return tokens


def _load_replacements(repo_root: Path, profile: Mapping[str, Any]) -> list[tuple[str, str]]:
    path = repo_root / "hosts" / str(profile["host_id"]) / str(profile["rewrites"])
    payload = _read_json(path)
    if payload.get("schema_version") != "avereth-host-rewrites/v1":
        raise ValueError(f"invalid host rewrite schema: {path}")
    replacements: list[tuple[str, str]] = []
    for entry in payload.get("replacements") or []:
        if not isinstance(entry, dict) or not isinstance(entry.get("from"), str):
            raise ValueError(f"invalid host rewrite entry: {path}")
        replacements.append((entry["from"], str(entry.get("to", ""))))
    return replacements


def render_text(
    content: str,
    *,
    tokens: Mapping[str, str],
    replacements: Sequence[tuple[str, str]] = (),
    source: str,
) -> str:
    rendered = content
    for key, value in tokens.items():
        marker = "{{" + key + "}}"
        if not value:
            rendered = re.sub(
                rf"(?m)^[ \t]*{re.escape(marker)}[ \t]*(?:\r?\n|$)",
                "",
                rendered,
            )
        rendered = rendered.replace(marker, value)
    for before, after in replacements:
        rendered = rendered.replace(before, after)
    unresolved = sorted(set(_TEMPLATE_TOKEN.findall(rendered)))
    if unresolved:
        raise ValueError(f"unresolved template token(s) in {source}: {', '.join(unresolved)}")
    return rendered


def _copy_skills(source: Path, destination: Path) -> None:
    def ignore(_directory: str, names: list[str]) -> set[str]:
        return {
            name
            for name in names
            if name in IGNORED_NAMES
            or name.endswith((".pyc", ".pyo"))
            or (name.startswith("test_") and name.endswith(".py"))
        }

    shutil.copytree(source, destination, ignore=ignore)


def _parse_agent_spec(path: Path) -> dict[str, str]:
    content = path.read_text(encoding="utf-8-sig")
    values: dict[str, str] = {}
    for key in ("name", "description", "permission_profile"):
        match = re.search(
            rf'^\s*{re.escape(key)}\s*=\s*"([^"]*)"\s*$',
            content,
            re.MULTILINE,
        )
        if not match:
            raise ValueError(f"agent spec lacks {key}: {path}")
        values[key] = match.group(1)
    instructions = re.search(
        r'^\s*instructions\s*=\s*"""(.*?)"""\s*$',
        content,
        re.MULTILINE | re.DOTALL,
    )
    if not instructions:
        raise ValueError(f"agent spec lacks instructions: {path}")
    values["instructions"] = instructions.group(1).strip("\n")
    return values


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _render_agent(
    spec: Mapping[str, str],
    profile: Mapping[str, Any],
    *,
    tokens: Mapping[str, str],
    replacements: Sequence[tuple[str, str]],
    source: str,
) -> str:
    instructions = render_text(
        spec["instructions"],
        tokens=tokens,
        replacements=replacements,
        source=source,
    )
    permission = (profile.get("permission_map") or {}).get(spec["permission_profile"])
    if not isinstance(permission, dict):
        raise ValueError(
            f"host {profile['host_id']} has no permission mapping for "
            f"{spec['permission_profile']!r}"
        )
    if profile["agent_format"] == "toml":
        if '"""' in instructions:
            raise ValueError(f"agent instructions contain an unsupported triple quote: {source}")
        lines = [
            f"name = {_toml_string(spec['name'])}",
            f"description = {_toml_string(spec['description'])}",
        ]
        if set(permission) != {"sandbox_mode"}:
            raise ValueError("Codex agent permission mapping must contain sandbox_mode")
        lines.append(f"sandbox_mode = {_toml_string(str(permission['sandbox_mode']))}")
        lines.extend(("", 'developer_instructions = """', instructions, '"""', ""))
        return "\n".join(lines)
    if profile["agent_format"] == "markdown":
        lines = [
            "---",
            f"name: {spec['name']}",
            f"description: {spec['description']}",
        ]
        if permission:
            if set(permission) != {"tools"}:
                raise ValueError("Claude agent permission mapping may contain only tools")
            lines.append(f"tools: {permission['tools']}")
        lines.extend(("---", "", instructions, ""))
        return "\n".join(lines)
    raise ValueError(f"unsupported agent format: {profile['agent_format']!r}")


def _render_agents(
    repo_root: Path,
    bundle_root: Path,
    profile: Mapping[str, Any],
    tokens: Mapping[str, str],
    replacements: Sequence[tuple[str, str]],
) -> None:
    manifest_path = repo_root / "agent-specs" / "manifest.json"
    manifest = _read_json(manifest_path)
    if manifest.get("schema_version") != "avereth-agent-spec-manifest/v1":
        raise ValueError(f"invalid agent manifest schema: {manifest_path}")
    target = bundle_root / "agents"
    target.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    for entry in manifest.get("agents") or []:
        if not isinstance(entry, dict):
            raise ValueError(f"invalid agent manifest entry: {manifest_path}")
        source_path = repo_root / "agent-specs" / str(entry["source"])
        spec = _parse_agent_spec(source_path)
        if spec["name"] != entry.get("name") or spec["name"] in seen:
            raise ValueError(f"agent manifest identity mismatch: {source_path}")
        seen.add(spec["name"])
        rendered = _render_agent(
            spec,
            profile,
            tokens=tokens,
            replacements=replacements,
            source=str(source_path),
        )
        output = target / (spec["name"] + str(profile["agent_extension"]))
        output.write_text(rendered, encoding="utf-8", newline="\n")


def _render_skill_templates(
    bundle_root: Path,
    *,
    tokens: Mapping[str, str],
    replacements: Sequence[tuple[str, str]],
) -> None:
    skills = bundle_root / "skills"
    for source in sorted(skills.rglob("*.source.md")):
        target = source.with_name(source.name.replace(".source.md", ".md"))
        target.write_text(
            render_text(
                source.read_text(encoding="utf-8-sig"),
                tokens=tokens,
                replacements=replacements,
                source=str(source),
            ),
            encoding="utf-8",
            newline="\n",
        )
        source.unlink()
    for path in sorted(skills.rglob("*.md")):
        content = path.read_text(encoding="utf-8-sig")
        rendered = render_text(
            content,
            tokens=tokens,
            replacements=replacements,
            source=str(path),
        )
        if rendered != content:
            path.write_text(rendered, encoding="utf-8", newline="\n")


def _apply_reference_renames(bundle_root: Path, profile: Mapping[str, Any]) -> None:
    for entry in profile.get("reference_renames") or []:
        source = bundle_root / str(entry["from"])
        target = bundle_root / str(entry["to"])
        if not source.is_file():
            raise ValueError(f"host reference source is missing: {source}")
        if target.exists():
            raise ValueError(f"host reference target already exists: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        source.replace(target)


def _apply_metadata_policy(bundle_root: Path, profile: Mapping[str, Any]) -> None:
    if profile.get("openai_metadata") is True:
        return
    for path in sorted((bundle_root / "skills").rglob("openai.yaml")):
        if path.parent.name != "agents":
            raise ValueError(f"refusing to remove unexpected metadata path: {path}")
        path.unlink()
    for directory in sorted((bundle_root / "skills").rglob("agents"), reverse=True):
        try:
            directory.rmdir()
        except OSError:
            pass


def _write_runtime_profile(bundle_root: Path, profile: Mapping[str, Any]) -> dict[str, Any]:
    payload = {
        "schema_version": RUNTIME_PROFILE_SCHEMA,
        "host_id": profile["host_id"],
        "default_runner": profile["default_runner"],
        "allowed_runners": profile["allowed_runners"],
        "discovery_channel": profile["discovery_channel"],
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    (bundle_root / "host_profile.json").write_text(rendered, encoding="utf-8")
    (bundle_root / "skills" / "cnki-paper" / "host_profile.json").write_text(
        rendered,
        encoding="utf-8",
    )
    return payload


def _digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def _write_manifest(bundle_root: Path, profile: Mapping[str, Any]) -> dict[str, Any]:
    files = {
        path.relative_to(bundle_root).as_posix(): _digest(path)
        for path in sorted(bundle_root.rglob("*"), key=lambda item: item.as_posix())
        if path.is_file() and path.name != "build-manifest.json"
    }
    payload = {
        "schema_version": MANIFEST_SCHEMA,
        "host_id": profile["host_id"],
        "default_runner": profile["default_runner"],
        "file_count": len(files),
        "files": files,
    }
    (bundle_root / "build-manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def _validate_output_target(repo_root: Path, output: Path) -> Path:
    repo_root = repo_root.resolve()
    unresolved = output.expanduser().absolute()
    if unresolved.is_symlink():
        raise ValueError(f"refusing symlink build output: {unresolved}")
    output = output.resolve()
    if output == repo_root or output in repo_root.parents:
        raise ValueError(f"refusing unsafe build output: {output}")
    if output.parent == output:
        raise ValueError(f"refusing filesystem-root build output: {output}")
    return output


def _validate_existing_output(output: Path, host: str) -> None:
    if not output.exists():
        return
    if not output.is_dir():
        raise ValueError(f"build output exists and is not a directory: {output}")
    if not any(output.iterdir()):
        return
    manifest_path = output / "build-manifest.json"
    try:
        manifest = _read_json(manifest_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(
            f"refusing to replace unmanaged non-empty build output: {output}"
        ) from exc
    if (
        manifest.get("schema_version") != MANIFEST_SCHEMA
        or manifest.get("host_id") != host
        or not isinstance(manifest.get("files"), dict)
    ):
        raise ValueError(
            f"refusing to replace mismatched build output for {host}: {output}"
        )


def build_host(repo_root: Path, host: str, output: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    output = _validate_output_target(repo_root, output)
    profile = load_profile(repo_root, host)
    tokens = _load_tokens(repo_root, profile)
    replacements = _load_replacements(repo_root, profile)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}-", dir=output.parent))
    try:
        _copy_skills(repo_root / "skills", temporary / "skills")
        _apply_reference_renames(temporary, profile)
        _render_skill_templates(
            temporary,
            tokens=tokens,
            replacements=replacements,
        )
        host_runtime = tokens.get("HOST_RUNTIME_DOCUMENT")
        if not host_runtime:
            raise ValueError(f"host runtime fragment is missing for {host}")
        (temporary / "skills" / "cnki-paper" / "references" / "host-runtime.md").write_text(
            host_runtime,
            encoding="utf-8",
            newline="\n",
        )
        _apply_metadata_policy(temporary, profile)
        _render_agents(repo_root, temporary, profile, tokens, replacements)
        entrypoint_source = repo_root / "entrypoints" / "avereth.source.md"
        entrypoint_target = temporary / str(profile["entrypoint_dir"]) / str(
            profile["entrypoint_file"]
        )
        entrypoint_target.parent.mkdir(parents=True, exist_ok=True)
        entrypoint_target.write_text(
            render_text(
                entrypoint_source.read_text(encoding="utf-8-sig"),
                tokens=tokens,
                replacements=replacements,
                source=str(entrypoint_source),
            ),
            encoding="utf-8",
            newline="\n",
        )
        _write_runtime_profile(temporary, profile)
        manifest = _write_manifest(temporary, profile)
        if output.exists():
            _validate_existing_output(output, host)
            shutil.rmtree(output)
        temporary.replace(output)
        return {
            "status": "PASS",
            "host": host,
            "output": str(output),
            "file_count": manifest["file_count"],
        }
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", choices=HOSTS, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        payload = build_host(args.repo_root, args.host, args.out)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"build error: {exc}")
        return 2
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(
            f"PASS: built {payload['host']} bundle with {payload['file_count']} files "
            f"at {payload['output']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
