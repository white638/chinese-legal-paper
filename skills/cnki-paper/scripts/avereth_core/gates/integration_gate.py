"""Read-only validation gate for optional Exa and Zotero support artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ..infrastructure.integration_contracts import (
    EXA_RUN_PATH_RE,
    load_json_object,
    validate_exa_manifest,
    validate_zotero_snapshot,
)


EXA_MANIFEST_REL = Path("reference_materials/integrations/exa_runs/manifest.json")
ZOTERO_SNAPSHOT_REL = Path("reference_materials/integrations/zotero_snapshot.json")
REGISTRY_REL = Path("reference_materials/literature_registry.json")


def _registry_uses_exa(registry: dict[str, Any] | None) -> bool:
    if not isinstance(registry, dict):
        return False
    queries = registry.get("queries")
    if isinstance(queries, list) and any(
        isinstance(query, dict)
        and str(query.get("channel") or "").strip().lower() == "exa"
        for query in queries
    ):
        return True
    sources = registry.get("sources")
    return isinstance(sources, list) and any(
        isinstance(source, dict) and source.get("discovery_events")
        for source in sources
    )


def _registry_uses_zotero(registry: dict[str, Any] | None) -> bool:
    if not isinstance(registry, dict):
        return False
    sources = registry.get("sources")
    return isinstance(sources, list) and any(
        isinstance(source, dict) and source.get("zotero_link") is not None
        for source in sources
    )


def _exa_registry_issues(
    manifest: dict[str, Any],
    registry: dict[str, Any] | None,
    workspace: Path,
) -> list[str]:
    if registry is None:
        return ["literature_registry.json is required when an Exa manifest is present"]
    raw_queries = registry.get("queries")
    if not isinstance(raw_queries, list):
        return ["literature_registry.json queries must be a list"]
    raw_runs = manifest.get("runs")
    if not isinstance(raw_runs, list):
        return []
    manifest_runs = {
        str(run.get("query_id") or "").strip(): run
        for run in raw_runs
        if isinstance(run, dict) and str(run.get("query_id") or "").strip()
    }
    exa_queries = {
        str(query.get("query_id") or "").strip(): query
        for query in raw_queries
        if isinstance(query, dict)
        and str(query.get("channel") or "").strip().lower() == "exa"
        and str(query.get("query_id") or "").strip()
    }
    issues: list[str] = []
    for query_id in sorted(set(manifest_runs) - set(exa_queries)):
        issues.append(f"manifest run {query_id!r} has no matching Exa registry query")
    for query_id in sorted(set(exa_queries) - set(manifest_runs)):
        issues.append(f"Exa registry query {query_id!r} has no matching manifest run")
    for query_id in sorted(set(manifest_runs) & set(exa_queries)):
        run = manifest_runs[query_id]
        query = exa_queries[query_id]
        query_path = str(query.get("run_artifact") or "").strip().replace("\\", "/")
        if query_path != run.get("path"):
            issues.append(
                f"Exa registry query {query_id!r} run_artifact does not match manifest"
            )
        if str(query.get("run_sha256") or "").strip().lower() != str(
            run.get("sha256") or ""
        ).strip().lower():
            issues.append(
                f"Exa registry query {query_id!r} run_sha256 does not match manifest"
            )

    raw_sources = registry.get("sources")
    if not isinstance(raw_sources, list):
        return [*issues, "literature_registry.json sources must be a list"]
    run_results: dict[str, list[dict[str, Any]]] = {}
    for query_id, run in manifest_runs.items():
        relative = str(run.get("path") or "").strip().replace("\\", "/")
        if not EXA_RUN_PATH_RE.fullmatch(relative):
            run_results[query_id] = []
            continue
        payload, _ = load_json_object(workspace / Path(relative))
        results = payload.get("results") if isinstance(payload, dict) else None
        run_results[query_id] = (
            [result for result in results if isinstance(result, dict)]
            if isinstance(results, list)
            else []
        )
    for source in raw_sources:
        if not isinstance(source, dict):
            continue
        source_id = str(source.get("source_id") or "").strip()
        events = source.get("discovery_events")
        if not isinstance(events, list):
            continue
        for number, event in enumerate(events, start=1):
            if not isinstance(event, dict) or str(
                event.get("provider") or ""
            ).strip().lower() != "exa":
                continue
            prefix = f"source {source_id} discovery event {number}"
            query_id = str(event.get("query_id") or "").strip()
            run = manifest_runs.get(query_id)
            if run is None:
                issues.append(f"{prefix} has no matching manifest run")
                continue
            if str(event.get("run_sha256") or "").strip().lower() != str(
                run.get("sha256") or ""
            ).strip().lower():
                issues.append(f"{prefix} run_sha256 does not match manifest")
            rank = event.get("rank")
            discovered_url = str(event.get("discovered_url") or "").strip()
            if not any(
                result.get("rank") == rank
                and str(result.get("url") or "").strip() == discovered_url
                for result in run_results.get(query_id, [])
            ):
                issues.append(f"{prefix} rank and URL do not match the Exa run")
    return issues


def _zotero_registry_issues(
    snapshot: dict[str, Any],
    registry: dict[str, Any] | None,
) -> list[str]:
    if registry is None:
        return ["literature_registry.json is required when a Zotero snapshot is present"]
    raw_sources = registry.get("sources")
    if not isinstance(raw_sources, list):
        return ["literature_registry.json sources must be a list"]
    sources = {
        str(source.get("source_id") or "").strip(): source
        for source in raw_sources
        if isinstance(source, dict) and str(source.get("source_id") or "").strip()
    }
    issues: list[str] = []
    server_id = str(snapshot.get("server_id") or "").strip()
    library_id = snapshot.get("library_id")
    raw_items = snapshot.get("items")
    if not isinstance(raw_items, list):
        return issues
    for number, item in enumerate(raw_items, start=1):
        if not isinstance(item, dict):
            continue
        source_id = str(item.get("source_id") or "").strip()
        source = sources.get(source_id)
        if source is None:
            issues.append(f"Zotero item {number} references unknown Source ID {source_id!r}")
            continue
        link = source.get("zotero_link")
        if not isinstance(link, dict):
            issues.append(
                f"Zotero item {number} source {source_id} has no canonical zotero_link"
            )
            continue
        expected = {
            "server_id": server_id,
            "library_id": library_id,
            "item_key": item.get("item_key"),
            "item_version": item.get("item_version"),
            "citation_key": item.get("citation_key"),
        }
        for field, value in expected.items():
            if link.get(field) != value:
                issues.append(
                    f"Zotero item {number} {field} does not match source {source_id} zotero_link"
                )
        if link.get("attachment_keys") != item.get("attachment_keys"):
            issues.append(
                f"Zotero item {number} attachment_keys do not match source {source_id} zotero_link"
            )
    snapshot_source_ids = {
        str(item.get("source_id") or "").strip()
        for item in raw_items
        if isinstance(item, dict)
    }
    for source_id, source in sources.items():
        if isinstance(source.get("zotero_link"), dict) and source_id not in snapshot_source_ids:
            issues.append(f"source {source_id} zotero_link has no matching snapshot item")
    return issues


def validate_integration_artifacts(outdir: Path) -> dict[str, Any]:
    issues: list[str] = []
    artifacts: dict[str, str] = {}
    registry, registry_load_issues = load_json_object(outdir / REGISTRY_REL)
    exa_path = outdir / EXA_MANIFEST_REL
    if exa_path.is_file():
        payload, load_issues = load_json_object(exa_path)
        artifact_issues = list(load_issues)
        if payload is not None:
            artifact_issues.extend(validate_exa_manifest(payload, workspace=outdir))
            if registry_load_issues:
                artifact_issues.extend(registry_load_issues)
            else:
                artifact_issues.extend(_exa_registry_issues(payload, registry, outdir))
        issues.extend(f"Exa manifest: {issue}" for issue in artifact_issues)
        artifacts[EXA_MANIFEST_REL.as_posix()] = (
            "invalid" if artifact_issues else "validated"
        )
    else:
        if _registry_uses_exa(registry):
            issues.append("Exa manifest: registry Exa provenance requires a manifest")
            artifacts[EXA_MANIFEST_REL.as_posix()] = "required-but-missing"
        else:
            artifacts[EXA_MANIFEST_REL.as_posix()] = "not-present"

    zotero_path = outdir / ZOTERO_SNAPSHOT_REL
    if zotero_path.is_file():
        payload, load_issues = load_json_object(zotero_path)
        artifact_issues = list(load_issues)
        if payload is not None:
            artifact_issues.extend(validate_zotero_snapshot(payload))
            if registry_load_issues:
                artifact_issues.extend(registry_load_issues)
            else:
                artifact_issues.extend(_zotero_registry_issues(payload, registry))
        issues.extend(f"Zotero snapshot: {issue}" for issue in artifact_issues)
        artifacts[ZOTERO_SNAPSHOT_REL.as_posix()] = (
            "invalid" if artifact_issues else "validated"
        )
    else:
        if _registry_uses_zotero(registry):
            issues.append("Zotero snapshot: registry zotero_link requires a snapshot")
            artifacts[ZOTERO_SNAPSHOT_REL.as_posix()] = "required-but-missing"
        else:
            artifacts[ZOTERO_SNAPSHOT_REL.as_posix()] = "not-present"

    return {
        "schema_version": "avereth-integration-validation/v1",
        "status": "PASS" if not issues else "FAIL",
        "artifacts": artifacts,
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("outdir", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = validate_integration_artifacts(args.outdir.resolve())
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Integration validation: {report['status']}")
        for issue in report["issues"]:
            print(f"- {issue}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
