#!/usr/bin/env python3
"""Build, validate, and recoverably install one Avereth host runtime."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence

from agent_bundle_check import validate_agent_bundle
from build_host import HOSTS, build_host, load_profile
from legacy_runtime_retirement import retire
from runtime_parity import compare
from smoke_check import smoke_check
from sync_runtime import sync


def _digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def default_runtime_home(repo_root: Path, host: str) -> Path:
    profile = load_profile(repo_root, host)
    override = os.environ.get(str(profile["home_env"]))
    return Path(override) if override else Path.home() / str(profile["default_home"])


def _copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def install_runtime(
    repo_root: Path,
    host: str,
    runtime_home: Path | None = None,
    backup_root: Path | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    if sys.version_info < (3, 10):
        raise RuntimeError("Avereth requires Python 3.10 or newer")
    profile = load_profile(repo_root, host)
    runtime_home = (runtime_home or default_runtime_home(repo_root, host)).resolve()
    if runtime_home.parent == runtime_home:
        raise ValueError(f"refusing filesystem-root runtime home: {runtime_home}")
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_root = (
        backup_root
        or runtime_home / "backups" / "avereth-v7" / stamp
    ).resolve()
    if backup_root == runtime_home or backup_root.parent == backup_root:
        raise ValueError(f"refusing unsafe backup root: {backup_root}")

    with tempfile.TemporaryDirectory(prefix=f"avereth-{host}-build-") as temporary:
        bundle = Path(temporary) / "bundle"
        build_payload = build_host(repo_root, host, bundle)
        smoke_errors, smoke_warnings = smoke_check(
            bundle,
            host,
            manifest_path=repo_root / "agent-specs" / "manifest.json",
        )
        if smoke_errors:
            raise RuntimeError("built bundle failed smoke check: " + "; ".join(smoke_errors))

        runtime_home.mkdir(parents=True, exist_ok=True)
        backup_root.mkdir(parents=True, exist_ok=True)
        retirement = retire(runtime_home, backup_root, host)
        skills_destination = runtime_home / "skills"
        agents_destination = runtime_home / "agents"
        entrypoint_dir = str(profile["entrypoint_dir"])
        entrypoint_file = str(profile["entrypoint_file"])
        entrypoint_destination = runtime_home / entrypoint_dir / entrypoint_file
        synchronization = sync(
            bundle / "skills",
            skills_destination,
            backup_root / "replaced-runtime",
        )
        agents_destination.mkdir(parents=True, exist_ok=True)
        for source in sorted((bundle / "agents").iterdir(), key=lambda item: item.name):
            if source.is_file():
                _copy_file(source, agents_destination / source.name)
        _copy_file(bundle / entrypoint_dir / entrypoint_file, entrypoint_destination)

        agent_errors = validate_agent_bundle(
            bundle / "agents",
            agents_destination,
            host=host,
            manifest_path=repo_root / "agent-specs" / "manifest.json",
        )
        if agent_errors:
            raise RuntimeError("installed agent parity failed: " + "; ".join(agent_errors))
        parity = compare(bundle / "skills", skills_destination)
        if parity["status"] != "PASS":
            raise RuntimeError("installed skill parity failed: " + json.dumps(parity, ensure_ascii=False))
        if _digest(bundle / entrypoint_dir / entrypoint_file) != _digest(entrypoint_destination):
            raise RuntimeError("installed entrypoint hash mismatch")

        controller = skills_destination / "cnki-paper" / "scripts" / "avereth.py"
        doctor = subprocess.run(
            [
                sys.executable,
                "-X",
                "utf8",
                str(controller),
                "--skills-dir",
                str(skills_destination),
                "doctor",
                "--json",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
        )
        if doctor.returncode != 0:
            raise RuntimeError(
                "installed doctor failed: "
                + " ".join((doctor.stdout + doctor.stderr).split())[-1000:]
            )
        try:
            doctor_payload = json.loads(doctor.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("installed doctor returned invalid JSON") from exc
        if doctor_payload.get("status") != "PASS":
            raise RuntimeError("installed doctor did not return PASS")

        return {
            "status": "PASS",
            "host": host,
            "runtime_home": str(runtime_home),
            "skills": str(skills_destination),
            "agents": str(agents_destination),
            "entrypoint": str(entrypoint_destination),
            "entrypoint_invocation": profile["entrypoint_invocation"],
            "backup_root": str(backup_root),
            "build_file_count": build_payload["file_count"],
            "runtime_files": parity["installed_files"],
            "retired_or_replaced": len(retirement["moved"]),
            "sync_changed": synchronization["changed"],
            "sync_removed": synchronization["removed"],
            "smoke_warnings": smoke_warnings,
        }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", choices=HOSTS, required=True)
    parser.add_argument("--runtime-home", type=Path)
    parser.add_argument("--backup-root", type=Path)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        payload = install_runtime(
            args.repo_root,
            args.host,
            args.runtime_home,
            args.backup_root,
        )
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"install error: {exc}")
        return 2
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"PASS: installed Avereth for {payload['host']} at {payload['runtime_home']}")
        print(f"Entrypoint: {payload['entrypoint_invocation']}")
        print(f"Recoverable backup: {payload['backup_root']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
