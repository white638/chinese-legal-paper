#!/usr/bin/env python3
"""Safely add the artifact-verified method-contract layer to v3/v2 workspaces.

Dry-run is the default.  Apply creates content-addressed backups and only adds
``needs-review`` placeholders; it never infers artifacts, diagnostics, or PASS
from legacy prose.  Rollback restores an explicitly named backup snapshot.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence


DESIGN_NAME = "research_design.json"
EXECUTION_NAME = "method_execution.json"
MIGRATION_REL = Path("migration/method_contract_v1")
REGISTRY_PATH = (
    Path(__file__).resolve().parent.parent
    / "references"
    / "method-adapter-registry.json"
)
RETIRED_TO_ACTIVE = {
    "text-as-data/measurement-v1": "text-as-data/measurement-v2",
    "text-alignment/v1": "text-alignment/v2",
    "text-matching/v1": "text-matching/v2",
}


class MigrationError(ValueError):
    """Raised when a method-contract migration cannot proceed safely."""


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _canonical_digest(value: Mapping[str, Any]) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _atomic_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(value)
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise MigrationError(f"Required file is missing: {path.name}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise MigrationError(f"Cannot read {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise MigrationError(f"{path.name} must contain a JSON object")
    return value


def _registry() -> Mapping[str, Any]:
    value = _load_json(REGISTRY_PATH)
    if value.get("schema_version") not in {
        "cnki-method-adapter-registry/v2",
        "cnki-method-adapter-registry/v3",
    }:
        raise MigrationError("Unsupported method-adapter registry schema")
    return value


def _required_schema(route: Mapping[str, Any], claim_types: set[str]) -> str:
    family = _text(route.get("family"))
    if family == "text_as_data":
        return "text-as-data/measurement-v2"
    if family == "process_tracing" and "causal_mechanism" in claim_types:
        return "process-tracing/v1"
    if family in {"quantitative", "experiment"} and "causal_effect" in claim_types:
        return "causal-design/v1"
    return ""


def _claim_types_by_route(design: Mapping[str, Any]) -> dict[str, set[str]]:
    values: dict[str, set[str]] = {}
    for claim in design.get("claims") or []:
        if not isinstance(claim, Mapping):
            continue
        for design_id in claim.get("design_ids") or []:
            values.setdefault(_text(design_id).upper(), set()).add(_text(claim.get("type")))
    return values


def _migrate_payloads(
    design: Mapping[str, Any],
    execution: Mapping[str, Any] | None,
    registry: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any] | None, list[str]]:
    if design.get("schema_version") not in {"cnki-research-design/v3", "cnki-research-design/v4"}:
        raise MigrationError("Method-contract migration requires cnki-research-design/v3 or v4")
    if execution is not None and execution.get("schema_version") not in {
        "cnki-method-execution/v2",
        "cnki-method-execution/v3",
    }:
        raise MigrationError("Method-contract migration only accepts cnki-method-execution/v2 or v3")
    contracts = registry.get("method_contracts") if isinstance(registry.get("method_contracts"), Mapping) else {}
    migrated_design = deepcopy(dict(design))
    changes: list[str] = []
    claim_types = _claim_types_by_route(migrated_design)
    routes: dict[str, dict[str, Any]] = {}
    for index, route in enumerate(migrated_design.get("method_routes") or []):
        if not isinstance(route, dict):
            continue
        route_id = _text(route.get("id")).upper()
        routes[route_id] = route
        original_schema_id = _text(route.get("method_contract_schema"))
        schema_id = original_schema_id or _required_schema(
            route, claim_types.get(route_id, set())
        )
        schema_id = RETIRED_TO_ACTIVE.get(schema_id, schema_id)
        if schema_id and schema_id not in contracts:
            raise MigrationError(f"Unknown required method contract: {schema_id}")
        revision = _text((contracts.get(schema_id) or {}).get("revision")) if schema_id else ""
        profile = _text(route.get("method_profile")) or schema_id
        if original_schema_id in RETIRED_TO_ACTIVE and profile == original_schema_id:
            profile = schema_id
        contract = route.get("method_contract") if isinstance(route.get("method_contract"), Mapping) else {}
        if original_schema_id in RETIRED_TO_ACTIVE:
            contract = {}
        if schema_id and not contract:
            contract = {
                key: f"needs-review: provide typed design fact for {key}"
                for key in (contracts[schema_id].get("design_required") or [])
            }
        expected = {
            "method_contract_schema": schema_id,
            "method_contract_revision": revision,
            "method_profile": profile,
            "method_contract": deepcopy(dict(contract)),
            "artifact_refs": deepcopy(route.get("artifact_refs"))
            if isinstance(route.get("artifact_refs"), list)
            else [],
        }
        for field, value in expected.items():
            if route.get(field) != value:
                route[field] = value
                changes.append(f"method_routes[{index}].{field}")
    if changes:
        migrated_design["status"] = "needs-review"
        log = migrated_design.get("change_log")
        if not isinstance(log, list):
            log = []
            migrated_design["change_log"] = log
        if not any(
            isinstance(item, Mapping) and item.get("event") == "method-contract-v1-migration"
            for item in log
        ):
            log.append(
                {
                    "event": "method-contract-v1-migration",
                    "status": "needs-review",
                    "note": "No artifact, diagnostic, metric, or PASS state was inferred from legacy prose.",
                }
            )

    migrated_execution = deepcopy(dict(execution)) if execution is not None else None
    if migrated_execution is not None:
        execution_changed = False
        for index, run in enumerate(migrated_execution.get("runs") or []):
            if not isinstance(run, dict):
                continue
            route = routes.get(_text(run.get("design_id")).upper())
            if route is None:
                continue
            contract = route.get("method_contract") if isinstance(route.get("method_contract"), Mapping) else {}
            result_types = sorted(
                {
                    _text(item.get("type"))
                    for item in run.get("results") or []
                    if isinstance(item, Mapping) and _text(item.get("type"))
                }
            )
            expected = {
                "method_contract_schema": _text(route.get("method_contract_schema")),
                "method_contract_revision": _text(route.get("method_contract_revision")),
                "method_profile": _text(route.get("method_profile")),
                "design_method_contract_sha256": _canonical_digest(contract),
                "method_contract": deepcopy(dict(contract)),
                "artifact_refs": deepcopy(run.get("artifact_refs"))
                if isinstance(run.get("artifact_refs"), list)
                else [],
                "inference_disposition": deepcopy(run.get("inference_disposition"))
                if isinstance(run.get("inference_disposition"), Mapping)
                else {
                    "status": "retained",
                    "reason_codes": ["MIGRATION_REVIEW_REQUIRED"],
                    "failed_diagnostic_ids": [],
                    "allowed_claim_types": result_types,
                    "prohibited_interpretations": [
                        _text(run.get("prohibited_inferences_observed"))
                        or "needs-review: recover prohibited interpretation boundary"
                    ],
                },
            }
            for field, value in expected.items():
                if run.get(field) != value:
                    run[field] = value
                    changes.append(f"runs[{index}].{field}")
                    execution_changed = True
        if execution_changed:
            migrated_execution["status"] = "needs-review"
            migrated_execution["migration"] = {
                "event": "method-contract-v1-migration",
                "status": "needs-review",
                "note": "Legacy execution text was not promoted to typed artifacts or diagnostics.",
            }
    return migrated_design, migrated_execution, sorted(set(changes))


def _snapshot(base: Path, files: Mapping[str, bytes]) -> str:
    digest = hashlib.sha256()
    for name in sorted(files):
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(files[name])
    snapshot_id = digest.hexdigest()[:16]
    root = base / MIGRATION_REL / "backups" / snapshot_id
    manifest = {
        "schema_version": "method-contract-migration-backup/v1",
        "snapshot_id": snapshot_id,
        "files": {
            name: {"sha256": _sha256_bytes(value), "size": len(value)}
            for name, value in sorted(files.items())
        },
    }
    for name, value in files.items():
        target = root / name
        if target.exists() and target.read_bytes() != value:
            raise MigrationError(f"Content-addressed backup collision for {snapshot_id}/{name}")
        if not target.exists():
            _atomic_bytes(target, value)
    _atomic_json(root / "manifest.json", manifest)
    return snapshot_id


def migrate_workspace(base: Path, *, apply: bool = False) -> Mapping[str, Any]:
    base = base.resolve()
    design_path = base / DESIGN_NAME
    execution_path = base / EXECUTION_NAME
    design = _load_json(design_path)
    execution = _load_json(execution_path) if execution_path.is_file() else None
    migrated_design, migrated_execution, changes = _migrate_payloads(design, execution, _registry())
    payload: dict[str, Any] = {
        "schema_version": "method-contract-migration-report/v1",
        "mode": "apply" if apply else "dry-run",
        "status": "needs-review" if changes else "already-current",
        "changes": changes,
        "snapshot_id": None,
    }
    if not apply or not changes:
        return payload
    files = {DESIGN_NAME: design_path.read_bytes()}
    if execution_path.is_file():
        files[EXECUTION_NAME] = execution_path.read_bytes()
    snapshot_id = _snapshot(base, files)
    _atomic_json(design_path, migrated_design)
    if migrated_execution is not None:
        _atomic_json(execution_path, migrated_execution)
    payload["snapshot_id"] = snapshot_id
    return payload


def rollback_workspace(base: Path, snapshot_id: str) -> Mapping[str, Any]:
    base = base.resolve()
    if not snapshot_id or any(character not in "0123456789abcdef" for character in snapshot_id):
        raise MigrationError("rollback requires an explicit hexadecimal snapshot ID")
    root = base / MIGRATION_REL / "backups" / snapshot_id
    manifest = _load_json(root / "manifest.json")
    if manifest.get("schema_version") != "method-contract-migration-backup/v1":
        raise MigrationError("Unsupported backup manifest schema")
    restored: list[str] = []
    for name, metadata in (manifest.get("files") or {}).items():
        if name not in {DESIGN_NAME, EXECUTION_NAME} or not isinstance(metadata, Mapping):
            raise MigrationError(f"Backup manifest contains unsafe target {name!r}")
        source = root / name
        value = source.read_bytes()
        if _sha256_bytes(value) != metadata.get("sha256"):
            raise MigrationError(f"Backup hash verification failed for {name}")
        _atomic_bytes(base / name, value)
        restored.append(name)
    return {
        "schema_version": "method-contract-migration-report/v1",
        "mode": "rollback",
        "status": "restored",
        "snapshot_id": snapshot_id,
        "restored": sorted(restored),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", help="Preview only (default)")
    group.add_argument("--apply", action="store_true")
    group.add_argument("--rollback", metavar="SNAPSHOT_ID")
    args = parser.parse_args(argv)
    try:
        payload = (
            rollback_workspace(args.path, args.rollback)
            if args.rollback
            else migrate_workspace(args.path, apply=args.apply)
        )
    except (MigrationError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
