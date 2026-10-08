#!/usr/bin/env python3
"""Read-only checks and explicit legal research tools; not a workflow controller."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys

from legal_core.common import (FILES, PROFILE, SKILL, LegalError, atomic_json, controller,
                               digest, file_hash, read_json, scoped)
from legal_core.validation import check_workspace, support_digest
from legal_core.templates import template


def doctor():
    issues = []
    try:
        controller()
        from avereth_core.infrastructure import legal_domain
        if getattr(legal_domain, "LEGAL_BRIDGE_VERSION", None) != 1:
            issues.append("cnki-paper legal bridge version is incompatible")
    except (ImportError, LegalError, RuntimeError):
        issues.append("Install the matching cnki-paper legal bridge; standalone copying is insufficient")
    for relative in ["assets/method-profiles.json", *[f"schemas/legal-{k}-v1.schema.json" for k in FILES]]:
        if not (SKILL / relative).is_file():
            issues.append("Missing bundled contract: " + relative)
    entrypoint = SKILL.parent / "cnki-paper" / "SKILL.md"
    return {"status": "FAIL" if issues else "PASS", "version": "1.0.0", "issues": issues,
            "layout": "runtime" if entrypoint.is_file() else "source_tree",
            "skill_entrypoint_available": entrypoint.is_file(),
            "warnings": [] if entrypoint.is_file() else ["Source tree: build/install a host runtime before using the skill entrypoint; source templates are not installed skills"],
            "credentials_present": {name: bool(os.environ.get(name)) for name in
                ("PKULAW_MCP_TOKEN", "OPENALEX_API_KEY", "SEMANTIC_SCHOLAR_API_KEY", "UNPAYWALL_EMAIL")},
            "network_tested": False, "controller": "cnki-paper"}


def enable(workspace, apply=False):
    root = Path(workspace).resolve()
    config_module, _ = controller()
    current = config_module.read_config(root)
    if current.path is None or current.issues:
        raise LegalError("CONFIG.REQUIRED", "First create/reconcile an existing cnki-paper workspace")
    if current.path.resolve() != scoped(root, "workflow_config.json"):
        raise LegalError("CONFIG.MIGRATION_REQUIRED", "Use cnki-paper migrate before enabling the legal profile")
    if doctor()["status"] != "PASS":
        raise LegalError("CONTROLLER.BRIDGE_REQUIRED", "Install the matching legal bridge before enabling")
    planned = {**current.payload, "legal_profile": PROFILE}
    problems = config_module.validate_workflow_config(planned)
    if problems:
        raise LegalError("CONFIG.INVALID", "; ".join(problems))
    new_sources = not scoped(root, FILES["sources"]).exists()
    result = {"status": "PREVIEW", "config": "workflow_config.json", "legal_profile": PROFILE,
              "initialize_sources": new_sources, "changes_applied": False}
    if not apply:
        return result
    from avereth_core.infrastructure.locks import exclusive_lock
    with exclusive_lock(root, ".avereth-transition.lock", "another workflow transition is active", operation="enable-legal-profile"):
        fresh = config_module.read_config(root)
        if fresh.payload != current.payload or fresh.issues:
            raise LegalError("CONFIG.CHANGED", "Configuration changed; inspect and retry")
        if current.payload.get("legal_profile") == PROFILE and not new_sources:
            return {**result, "status": "UNCHANGED"}
        backup = scoped(root, "legal_backups/" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "/workflow_config.json")
        backup.parent.mkdir(parents=True, exist_ok=False)
        shutil.copy2(current.path, backup)
        atomic_json(current.path, planned)
        if new_sources:
            data = template("sources")
            data["scope_reason"] = "已启用法学研究；等待登记实际来源与核验记录。"
            atomic_json(scoped(root, FILES["sources"]), data)
        return {**result, "status": "ENABLED", "changes_applied": True,
                "backup": backup.relative_to(root).as_posix(), "completion_receipt_created": False}


def bindings(workspace):
    root = Path(workspace)
    registry = read_json(scoped(root, "reference_materials/literature_registry.json"))
    records = {r["source_id"]: r for r in registry.get("sources", [])}
    design_path = scoped(root, "research_design.json")
    claims = {c["id"]: c for c in read_json(design_path).get("claims", [])} if design_path.is_file() else {}
    result = {"source_digests": {k: digest(v) for k, v in records.items()},
              "claim_digests": {k: digest(v) for k, v in claims.items()}, "support_digests": {},
              "warning": "Digests prove binding only. Do not mark support verified without reading and evaluating the sources."}
    path = scoped(root, FILES["citations"])
    if path.exists():
        for row in read_json(path).get("entries", []):
            result["support_digests"][row["citation_id"]] = support_digest(row, records.get(row["source_id"]), claims.get(row.get("claim_id")))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="Check installation; never sends credentials or network requests")
    p = sub.add_parser("enable", help="Preview or explicitly enable an existing workspace")
    p.add_argument("workspace"); p.add_argument("--apply", action="store_true")
    p = sub.add_parser("check", help="Run structural and binding checks through the selected stage")
    p.add_argument("workspace"); p.add_argument("--stage", default="audit")
    p = sub.add_parser("template", help="Print incomplete contracts; never writes a verified record")
    p.add_argument("name", choices=["sources", "source", "analysis", "claim", "citations", "citation", "review"])
    p.add_argument("--method", default="doctrinal")
    p = sub.add_parser("bindings", help="Inspect source/claim/support digests without altering reviews")
    p.add_argument("workspace")
    p = sub.add_parser("hash", help="Hash a local artifact without claiming its contents verified")
    p.add_argument("path")
    p = sub.add_parser("search", help="Query a metadata provider; returns candidates only")
    p.add_argument("provider", choices=["crossref", "openalex", "semantic-scholar", "unpaywall"])
    p.add_argument("query"); p.add_argument("--limit", type=int, default=10); p.add_argument("--cursor")
    p = sub.add_parser("pkulaw-discover", help="Initialize MCP and list actual subscribed tools")
    p.add_argument("endpoint")
    p = sub.add_parser("pkulaw-call", help="Explicitly call one discovered tool with a bounded attempt ledger")
    for name in ("workspace", "endpoint", "tool", "arguments_file"):
        p.add_argument(name)
    p.add_argument("--schema-digest", required=True)
    p.add_argument("--allow-tool", action="append", required=True)
    p.add_argument("--unit-cost", required=True, help="Account-confirmed estimated CNY per attempt; not a provider-enforced price cap")
    p.add_argument("--budget", required=True); p.add_argument("--max-calls", type=int, required=True)
    p.add_argument("--ledger", default="reference_materials/integrations/pkulaw_budget.json")
    p = sub.add_parser("render-notes", help="Print verified working-draft Markdown footnote definitions")
    p.add_argument("workspace")
    p = sub.add_parser("audit-docx", help="Check native footnotes, not legal correctness or rendered layout")
    p.add_argument("path")
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            result = doctor()
        elif args.command == "enable":
            result = enable(args.workspace, args.apply)
        elif args.command == "check":
            result = check_workspace(args.workspace, stage=args.stage)
        elif args.command == "template":
            result = template(args.name, args.method)
        elif args.command == "bindings":
            result = bindings(args.workspace)
        elif args.command == "hash":
            result = {"sha256": file_hash(args.path), "path": str(Path(args.path).resolve())}
        elif args.command == "search":
            from legal_core.providers import search
            result = search(args.provider, args.query, limit=args.limit, cursor=args.cursor)
        elif args.command in {"pkulaw-discover", "pkulaw-call"}:
            from legal_core.pkulaw import Client
            client = Client(args.endpoint)
            discovered = client.discover()
            if args.command == "pkulaw-discover":
                result = discovered
            else:
                result = client.call(args.tool, read_json(args.arguments_file), schema_digest=args.schema_digest,
                    allow_tools=args.allow_tool, ledger=scoped(args.workspace, args.ledger), unit_cost=args.unit_cost,
                    budget=args.budget, max_calls=args.max_calls)
        elif args.command == "render-notes":
            from legal_core.citations import render_notes
            print(render_notes(args.workspace), end="")
            return 0
        elif args.command == "audit-docx":
            from legal_core.citations import audit_docx
            result = audit_docx(args.path)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 1 if result.get("status") == "FAIL" else 0
    except (LegalError, OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        print(json.dumps({"status": "FAIL", "code": getattr(exc, "code", "INPUT.INVALID"),
                          "message": str(exc) if isinstance(exc, LegalError) else f"Operation failed ({type(exc).__name__})"}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
