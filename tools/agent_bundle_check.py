#!/usr/bin/env python3
"""Validate a built Avereth agent bundle and optional installed parity."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from tools.legacy_runtime_retirement import retired_agent_names
except ModuleNotFoundError:  # Direct execution from the tools directory.
    from legacy_runtime_retirement import retired_agent_names

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 compatibility.
    tomllib = None  # type: ignore[assignment]


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = ROOT / "agent-specs" / "manifest.json"
HOST_EXTENSIONS = {"codex": ".toml", "claude": ".md"}


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return payload


def _parse_source_spec(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8-sig")
    values: dict[str, str] = {}
    for key in ("name", "description", "permission_profile"):
        match = re.search(
            rf'^\s*{re.escape(key)}\s*=\s*"([^"]*)"\s*$', text, re.MULTILINE
        )
        if not match:
            raise ValueError(f"agent spec lacks {key}: {path}")
        values[key] = match.group(1)
    instructions = re.search(
        r'^\s*instructions\s*=\s*"""(.*?)"""\s*$',
        text,
        re.MULTILINE | re.DOTALL,
    )
    if not instructions:
        raise ValueError(f"agent spec lacks instructions: {path}")
    values["instructions"] = instructions.group(1).strip()
    return values


def load_contracts(manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, dict[str, Any]]:
    manifest_path = manifest_path.resolve()
    payload = _read_json(manifest_path)
    if payload.get("schema_version") != "avereth-agent-spec-manifest/v1":
        raise ValueError(f"invalid agent manifest schema: {manifest_path}")
    contracts: dict[str, dict[str, Any]] = {}
    for entry in payload.get("agents") or []:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            raise ValueError(f"invalid agent manifest entry: {manifest_path}")
        source_path = manifest_path.parent / str(entry.get("source") or "")
        source = _parse_source_spec(source_path)
        name = str(entry["name"])
        if source["name"] != name or name in contracts:
            raise ValueError(f"agent manifest identity mismatch: {source_path}")
        phrases = entry.get("phrases")
        if not isinstance(phrases, list) or not all(isinstance(item, str) for item in phrases):
            raise ValueError(f"invalid agent phrase contract: {source_path}")
        contracts[name] = {
            **source,
            "phrases": tuple(phrases),
            "source": source_path,
        }
    if not contracts:
        raise ValueError(f"agent manifest contains no agents: {manifest_path}")
    return contracts


def expected_filenames(
    host: str,
    manifest_path: Path = DEFAULT_MANIFEST,
) -> tuple[str, ...]:
    if host not in HOST_EXTENSIONS:
        raise ValueError(f"unsupported host: {host!r}")
    extension = HOST_EXTENSIONS[host]
    return tuple(name + extension for name in load_contracts(manifest_path))


def _fallback_toml(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for key in ("name", "description", "sandbox_mode"):
        match = re.search(rf'^\s*{key}\s*=\s*"([^"]*)"\s*$', text, re.MULTILINE)
        if match:
            data[key] = match.group(1)
    instructions = re.search(
        r'^\s*developer_instructions\s*=\s*"""(.*?)"""\s*$',
        text,
        re.MULTILINE | re.DOTALL,
    )
    if instructions:
        data["developer_instructions"] = instructions.group(1)
    return data


def _load_codex_agent(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8", errors="strict")
    parsed = _fallback_toml(text) if tomllib is None else tomllib.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("TOML root must be a table")
    instructions = parsed.get("developer_instructions")
    return parsed, instructions if isinstance(instructions, str) else ""


def _load_claude_agent(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8", errors="strict")
    front = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.DOTALL)
    if not front:
        raise ValueError("Markdown agent lacks YAML frontmatter")
    metadata: dict[str, str] = {}
    for line in front.group(1).splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)", line)
        if not match:
            raise ValueError(f"unsupported YAML frontmatter line: {line!r}")
        metadata[match.group(1)] = match.group(2).strip()
    return metadata, front.group(2)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _permission_error(
    host: str,
    filename: str,
    config: Mapping[str, Any],
    permission_profile: str,
) -> str | None:
    if host == "codex":
        expected = "workspace-write" if permission_profile == "workspace_write" else "read-only"
        if config.get("sandbox_mode") != expected:
            return f"{filename}: sandbox_mode must be {expected!r}"
        return None
    tools = config.get("tools")
    if permission_profile == "read_only" and tools != "Read":
        return f"{filename}: read-only Claude agents must declare tools: Read"
    if permission_profile == "workspace_write" and tools is not None:
        return f"{filename}: primary Claude agent must inherit host tools"
    return None


def validate_agent_bundle(
    bundle_dir: Path,
    installed_dir: Path | None = None,
    *,
    host: str = "codex",
    manifest_path: Path = DEFAULT_MANIFEST,
) -> list[str]:
    errors: list[str] = []
    if host not in HOST_EXTENSIONS:
        return [f"unsupported host: {host!r}"]
    try:
        contracts = load_contracts(manifest_path)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        return [f"agent contract load failed: {exc}"]
    bundle_dir = bundle_dir.resolve()
    if not bundle_dir.is_dir():
        return [f"built agents directory is missing: {bundle_dir}"]

    extension = HOST_EXTENSIONS[host]
    expected = {name + extension for name in contracts}
    actual = {path.name for path in bundle_dir.iterdir() if path.is_file()}
    for filename in sorted(expected - actual):
        errors.append(f"built agent missing: {filename}")
    retired = set(retired_agent_names())
    for filename in sorted(actual & retired):
        errors.append(f"retired agent is still present: {filename}")
    for filename in sorted(actual - expected - retired):
        errors.append(f"unexpected built agent file: {filename}")

    for name, contract in contracts.items():
        filename = name + extension
        path = bundle_dir / filename
        if not path.is_file():
            continue
        try:
            if host == "codex":
                config, instructions = _load_codex_agent(path)
                required = {"name", "description", "sandbox_mode", "developer_instructions"}
                allowed = required
            else:
                config, instructions = _load_claude_agent(path)
                required = {"name", "description"}
                allowed = required | {"tools"}
        except (OSError, UnicodeError, ValueError) as exc:
            errors.append(f"{filename}: invalid {host} agent format or UTF-8: {exc}")
            continue
        missing = required - set(config)
        if missing:
            errors.append(f"{filename}: missing required keys: {', '.join(sorted(missing))}")
        unexpected = set(config) - allowed
        if unexpected:
            errors.append(f"{filename}: unexpected metadata keys: {', '.join(sorted(unexpected))}")
        if config.get("name") != name:
            errors.append(f"{filename}: name must be {name!r}")
        description = config.get("description")
        if not isinstance(description, str) or len(description.strip()) < 40:
            errors.append(f"{filename}: description is missing or too short")
        permission_error = _permission_error(
            host, filename, config, str(contract["permission_profile"])
        )
        if permission_error:
            errors.append(permission_error)
        if len(instructions.strip()) < 300:
            errors.append(f"{filename}: instructions are missing or too short")
            continue
        lowered = instructions.lower()
        for phrase in contract["phrases"]:
            if str(phrase).lower() not in lowered:
                errors.append(f"{filename}: missing boundary phrase {phrase!r}")
        if "model" in config or "model_reasoning_effort" in config:
            errors.append(f"{filename}: model settings must inherit from the parent session")

    if installed_dir is not None:
        installed_dir = installed_dir.resolve()
        if not installed_dir.is_dir():
            errors.append(f"installed agents directory is missing: {installed_dir}")
        else:
            installed_actual = {path.name for path in installed_dir.iterdir() if path.is_file()}
            for filename in sorted(expected):
                source = bundle_dir / filename
                installed = installed_dir / filename
                if not installed.is_file():
                    errors.append(f"installed agent missing: {filename}")
                elif source.is_file() and _sha256(source) != _sha256(installed):
                    errors.append(f"installed agent hash mismatch: {filename}")
            for filename in sorted(installed_actual & retired):
                errors.append(f"retired installed agent is still present: {filename}")
    return errors


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle_agents", type=Path)
    parser.add_argument("installed_agents", nargs="?", type=Path)
    parser.add_argument("--host", choices=tuple(HOST_EXTENSIONS), default="codex")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args(argv)
    errors = validate_agent_bundle(
        args.bundle_agents,
        args.installed_agents,
        host=args.host,
        manifest_path=args.manifest,
    )
    for message in errors:
        print(f"ERROR {message}")
    if errors:
        print(f"FAIL: {len(errors)} agent bundle error(s)")
        return 1
    count = len(load_contracts(args.manifest))
    suffix = "; installed parity verified" if args.installed_agents is not None else ""
    print(f"PASS: {count} {args.host} agent(s){suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
