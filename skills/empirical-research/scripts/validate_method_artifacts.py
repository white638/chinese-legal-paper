#!/usr/bin/env python3
"""Validate typed method contracts against hash-registered artifacts.

The validator checks structure, data identities, recomputability, diagnostic
consistency, and inference-overreach.  It never produces a universal quality
score and never applies a universal F1, sample-size, p-value, or agreement
threshold.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from method_contract_loader import (
    ContractLoaderError,
    load_registry,
    supplemental_profile_binding,
    validate_core_contract,
    validate_supplemental_contract,
)
from validators import Finding, ValidationContext
from validators import causal_design, event_history, institutional_grammar, network
from validators import process_tracing, text_alignment, text_measurement


HERE = Path(__file__).resolve().parent

VALIDATORS = {
    "text_measurement": text_measurement.validate,
    "text_alignment": text_alignment.validate,
    "event_history": event_history.validate,
    "causal_design": causal_design.validate,
    "process_tracing": process_tracing.validate,
    "institutional_grammar": institutional_grammar.validate,
    "network": network.validate,
}


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _digest(value: Mapping[str, Any]) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _schema_finding_code(code: str, *, supplemental: bool) -> str:
    if code.startswith("PTP."):
        return code
    if code == "SUPPLEMENTAL.RESERVED_AUTHORITY":
        return "ME.SUPPLEMENTAL.RESERVED_AUTHORITY"
    suffix = code.removeprefix("SCHEMA.")
    namespace = "ME.SUPPLEMENTAL.SCHEMA" if supplemental else "ME.CONTRACT.SCHEMA"
    return f"{namespace}_{suffix}"


def _pointer_path(prefix: str, pointer: str) -> str:
    if pointer in {"", "/"}:
        return prefix
    tokens = [
        token.replace("~1", "/").replace("~0", "~")
        for token in pointer.lstrip("/").split("/")
    ]
    rendered = prefix
    for token in tokens:
        rendered += f"[{token}]" if token.isdigit() else f".{token}"
    return rendered


def _schema_findings(
    issues: Sequence[Mapping[str, str]],
    *,
    prefix: str,
    supplemental: bool,
) -> list[Finding]:
    return [
        Finding(
            _schema_finding_code(_text(issue.get("code")), supplemental=supplemental),
            "ERROR",
            _text(issue.get("message")),
            _pointer_path(prefix, _text(issue.get("path"))),
        )
        for issue in issues
    ]


def required_contract_ids(route: Mapping[str, Any], run: Mapping[str, Any]) -> set[str]:
    family = _text(route.get("family"))
    result_types = {
        _text(item.get("type"))
        for item in run.get("results") or []
        if isinstance(item, Mapping)
    }
    required: set[str] = set()
    if family == "text_as_data":
        required.add("text-as-data/measurement-v2")
    if "causal_effect" in result_types:
        required.add("@causal-effect")
    if family == "process_tracing" and "causal_mechanism" in result_types:
        required.add("process-tracing/v1")
    return required


def validate_run_contract(
    base: Path,
    route: Mapping[str, Any],
    run: Mapping[str, Any],
    *,
    path: str,
) -> list[Finding]:
    findings: list[Finding] = []
    registry = load_registry()
    contracts = (
        registry.get("method_contracts")
        if isinstance(registry.get("method_contracts"), Mapping)
        else {}
    )
    schema_id = _text(run.get("method_contract_schema"))
    route_schema = _text(route.get("method_contract_schema"))
    route_supplemental_id = _text(route.get("supplemental_profile_id"))
    run_supplemental_id = _text(run.get("supplemental_profile_id"))
    route_supplemental_present = any(
        field in route
        for field in ("supplemental_profile_id", "supplemental_contract")
    )
    run_supplemental_present = any(
        field in run
        for field in (
            "supplemental_profile_id",
            "supplemental_contract",
            "design_supplemental_contract_sha256",
        )
    )
    if route_supplemental_present and not route_supplemental_id:
        findings.append(
            Finding(
                "ME.SUPPLEMENTAL.DESIGN_PROFILE_MISSING",
                "ERROR",
                "Any supplemental design field requires a registered supplemental_profile_id",
                f"{path}.supplemental_profile_id",
            )
        )
    if run_supplemental_present and not run_supplemental_id:
        findings.append(
            Finding(
                "ME.SUPPLEMENTAL.PROFILE_MISSING",
                "ERROR",
                "Any supplemental execution field requires a registered supplemental_profile_id",
                f"{path}.supplemental_profile_id",
            )
        )
    if route_supplemental_present and not route_schema:
        findings.append(
            Finding(
                "ME.SUPPLEMENTAL.DESIGN_CORE_MISSING",
                "ERROR",
                "Any supplemental design field requires a non-empty core method_contract_schema",
                f"{path}.method_contract_schema",
            )
        )
    if run_supplemental_present and not schema_id:
        findings.append(
            Finding(
                "ME.SUPPLEMENTAL.CORE_MISSING",
                "ERROR",
                "Any supplemental execution field requires a non-empty core method_contract_schema",
                f"{path}.method_contract_schema",
            )
        )
    if route_supplemental_present and not _text(route.get("method_contract_revision")):
        findings.append(
            Finding(
                "ME.SUPPLEMENTAL.DESIGN_CORE_REVISION_MISSING",
                "ERROR",
                "Any supplemental design field requires a non-empty core method_contract_revision",
                f"{path}.method_contract_revision",
            )
        )
    if run_supplemental_present and not _text(run.get("method_contract_revision")):
        findings.append(
            Finding(
                "ME.SUPPLEMENTAL.CORE_REVISION_MISSING",
                "ERROR",
                "Any supplemental execution field requires a non-empty core method_contract_revision",
                f"{path}.method_contract_revision",
            )
        )
    binding_cache: dict[str, tuple[str, str] | None] = {}
    for side, supplemental_id, declared_schema, declared_revision in (
        (
            "design",
            route_supplemental_id,
            route_schema,
            _text(route.get("method_contract_revision")),
        ),
        (
            "execution",
            run_supplemental_id,
            schema_id,
            _text(run.get("method_contract_revision")),
        ),
    ):
        if not supplemental_id:
            continue
        try:
            if supplemental_id not in binding_cache:
                binding_cache[supplemental_id] = supplemental_profile_binding(
                    registry, supplemental_id
                )
            binding = binding_cache[supplemental_id]
            if binding is None:
                continue
            supplemental_core_id, supplemental_core_revision = binding
        except ContractLoaderError as exc:
            binding_cache[supplemental_id] = None
            findings.append(
                Finding(
                    "ME.SUPPLEMENTAL.PROFILE_UNREGISTERED",
                    "ERROR",
                    str(exc),
                    f"{path}.supplemental_profile_id",
                )
            )
            continue
        if declared_schema and declared_schema != supplemental_core_id:
            findings.append(
                Finding(
                    (
                        "ME.SUPPLEMENTAL.DESIGN_CORE_MISMATCH"
                        if side == "design"
                        else "ME.SUPPLEMENTAL.CORE_MISMATCH"
                    ),
                    "ERROR",
                    f"Supplemental profile {supplemental_id!r} requires core {supplemental_core_id!r}",
                    f"{path}.method_contract_schema",
                )
            )
        if declared_revision and declared_revision != supplemental_core_revision:
            findings.append(
                Finding(
                    (
                        "ME.SUPPLEMENTAL.DESIGN_CORE_REVISION_MISMATCH"
                        if side == "design"
                        else "ME.SUPPLEMENTAL.CORE_REVISION_MISMATCH"
                    ),
                    "ERROR",
                    f"Supplemental profile {supplemental_id!r} requires core revision {supplemental_core_revision!r}",
                    f"{path}.method_contract_revision",
                )
            )
    if _text(run.get("status")) in {"not-applicable", "withdrawn"}:
        return findings
    required = required_contract_ids(route, run)
    causal_ids = {
        "causal-design/v1",
        "causal-panel/v1",
        "event-history/v1",
        "text-matching/v2",
    }
    if "@causal-effect" in required:
        required.remove("@causal-effect")
        if schema_id not in causal_ids:
            findings.append(
                Finding(
                    "ME.INFERENCE.CAUSAL_CONTRACT_MISSING",
                    "ERROR",
                    "causal_effect requires an estimand/counterfactual diagnostic contract",
                    f"{path}.method_contract_schema",
                )
            )
    if required and schema_id not in required:
        findings.append(
            Finding(
                "ME.CONTRACT.REQUIRED_PROFILE_MISSING",
                "ERROR",
                "Execution requires typed method contract: " + ", ".join(sorted(required)),
                f"{path}.method_contract_schema",
            )
        )
    if not schema_id:
        return findings
    spec = contracts.get(schema_id)
    if not isinstance(spec, Mapping):
        retired = registry.get("retired_method_contracts")
        retired_spec = retired.get(schema_id) if isinstance(retired, Mapping) else None
        if isinstance(retired_spec, Mapping):
            successor = _text(retired_spec.get("successor"))
            findings.append(
                Finding(
                    "ME.CONTRACT.MIGRATION_REQUIRED",
                    "ERROR",
                    f"Retired method contract {schema_id!r} requires explicit migration to {successor!r}",
                    f"{path}.method_contract_schema",
                )
            )
            return findings
        findings.append(
            Finding(
                "ME.CONTRACT.SCHEMA_UNKNOWN",
                "ERROR",
                f"Unknown method_contract_schema {schema_id!r}",
                f"{path}.method_contract_schema",
            )
        )
        return findings
    family = _text(route.get("family"))
    families = registry.get("families") if isinstance(registry.get("families"), Mapping) else {}
    allowed_families = {
        name
        for name, adapter in families.items()
        if isinstance(adapter, Mapping)
        and schema_id in set(adapter.get("method_contract_profiles") or [])
    }
    if family not in allowed_families:
        findings.append(
            Finding(
                "ME.CONTRACT.FAMILY_MISMATCH",
                "ERROR",
                f"{schema_id} is not registered for route family {family!r}",
                f"{path}.method_contract_schema",
            )
        )
    if route_schema and route_schema != schema_id:
        findings.append(
            Finding(
                "ME.CONTRACT.DESIGN_DRIFT",
                "ERROR",
                "Execution method-contract schema differs from the confirmed design",
                f"{path}.method_contract_schema",
            )
        )
    if _text(run.get("method_contract_revision")) != _text(spec.get("revision")):
        findings.append(
            Finding(
                "ME.CONTRACT.REVISION_MISMATCH",
                "ERROR",
                "Execution method-contract revision differs from the active registry",
                f"{path}.method_contract_revision",
            )
        )
    if _text(run.get("method_profile")) != _text(route.get("method_profile")):
        findings.append(
            Finding(
                "ME.CONTRACT.PROFILE_DRIFT",
                "ERROR",
                "Execution method_profile differs from the confirmed design",
                f"{path}.method_profile",
            )
        )
    route_contract = route.get("method_contract") if isinstance(route.get("method_contract"), Mapping) else {}
    declared_digest = _text(run.get("design_method_contract_sha256")).casefold()
    expected_digest = _digest(route_contract)
    if declared_digest != expected_digest:
        findings.append(
            Finding(
                "ME.CONTRACT.DESIGN_DRIFT",
                "ERROR",
                "Typed design contract changed after the execution run was scaffolded",
                f"{path}.design_method_contract_sha256",
            )
        )
    contract = run.get("method_contract")
    if not isinstance(contract, Mapping):
        findings.append(
            Finding(
                "ME.CONTRACT.MISSING",
                "ERROR",
                "method_contract must be a typed object",
                f"{path}.method_contract",
            )
        )
        return findings
    findings.extend(
        _schema_findings(
            validate_core_contract(
                registry,
                schema_id,
                contract,
                phase="execution",
            ),
            prefix=f"{path}.method_contract",
            supplemental=False,
        )
    )
    for key in spec.get("design_required") or []:
        if key not in route_contract:
            findings.append(
                Finding(
                    "ME.CONTRACT.DESIGN_INCOMPLETE",
                    "ERROR",
                    f"Confirmed design contract lacks required key {key!r}",
                    f"{path}.method_contract.{key}",
                )
            )
    refs = run.get("artifact_refs")
    if not isinstance(refs, list):
        findings.append(
            Finding(
                "ME.CONTRACT.ARTIFACT_REFS_INVALID",
                "ERROR",
                "artifact_refs must be an array of registered Artifact IDs",
                f"{path}.artifact_refs",
            )
        )
        refs = []
    artifacts = {
        _text(item.get("id")).upper(): item
        for item in run.get("artifacts") or []
        if isinstance(item, Mapping) and _text(item.get("id"))
    }
    unknown_refs = sorted({_text(item).upper() for item in refs if _text(item)} - set(artifacts))
    if unknown_refs:
        findings.append(
            Finding(
                "ME.CONTRACT.ARTIFACT_UNRESOLVED",
                "ERROR",
                "artifact_refs contains unknown IDs: " + ", ".join(unknown_refs),
                f"{path}.artifact_refs",
            )
        )

    route_supplemental = (
        route.get("supplemental_contract")
        if isinstance(route.get("supplemental_contract"), Mapping)
        else {}
    )
    run_supplemental = run.get("supplemental_contract")
    if route_supplemental_id != run_supplemental_id:
        findings.append(
            Finding(
                "ME.SUPPLEMENTAL.DESIGN_DRIFT",
                "ERROR",
                "Execution supplemental profile differs from the confirmed design",
                f"{path}.supplemental_profile_id",
            )
        )
    if not run_supplemental_id:
        if run_supplemental or route_supplemental:
            findings.append(
                Finding(
                    "ME.SUPPLEMENTAL.PROFILE_MISSING",
                    "ERROR",
                    "A supplemental_contract requires a registry-selected supplemental_profile_id",
                    f"{path}.supplemental_profile_id",
                )
            )
    else:
        if not isinstance(run_supplemental, Mapping):
            findings.append(
                Finding(
                    "ME.SUPPLEMENTAL.CONTRACT_MISSING",
                    "ERROR",
                    "supplemental_contract must be an object",
                    f"{path}.supplemental_contract",
                )
            )
        else:
            declared_supplemental_digest = _text(
                run.get("design_supplemental_contract_sha256")
            ).casefold()
            expected_supplemental_digest = _digest(route_supplemental)
            if declared_supplemental_digest != expected_supplemental_digest:
                findings.append(
                    Finding(
                        "ME.SUPPLEMENTAL.DESIGN_DRIFT",
                        "ERROR",
                        "Supplemental design contract changed after execution was scaffolded",
                        f"{path}.design_supplemental_contract_sha256",
                    )
                )
            try:
                supplemental_issues, supplemental_refs = validate_supplemental_contract(
                    registry,
                    schema_id,
                    _text(spec.get("revision")),
                    run_supplemental_id,
                    run_supplemental,
                )
            except ContractLoaderError as exc:
                findings.append(
                    Finding(
                        "ME.SUPPLEMENTAL.PROFILE_UNREGISTERED",
                        "ERROR",
                        str(exc),
                        f"{path}.supplemental_profile_id",
                    )
                )
                supplemental_issues, supplemental_refs = [], set()
            findings.extend(
                _schema_findings(
                    supplemental_issues,
                    prefix=f"{path}.supplemental_contract",
                    supplemental=True,
                )
            )
            declared_refs = {_text(item).upper() for item in refs if _text(item)}
            missing_declared = sorted(supplemental_refs - declared_refs)
            if missing_declared:
                findings.append(
                    Finding(
                        "ME.SUPPLEMENTAL.ARTIFACT_REF_MISSING",
                        "ERROR",
                        "Supplemental Artifact IDs are absent from artifact_refs: "
                        + ", ".join(missing_declared),
                        f"{path}.artifact_refs",
                    )
                )
            missing_records = sorted(supplemental_refs - set(artifacts))
            if missing_records:
                findings.append(
                    Finding(
                        "ME.SUPPLEMENTAL.ARTIFACT_UNRESOLVED",
                        "ERROR",
                        "Supplemental Artifact IDs have no run artifact record: "
                        + ", ".join(missing_records),
                        f"{path}.artifacts",
                    )
                )
    validator = VALIDATORS.get(_text(spec.get("validator")))
    if validator is None:
        findings.append(
            Finding(
                "ME.CONTRACT.VALIDATOR_MISSING",
                "ERROR",
                f"No validator is registered for {schema_id}",
                f"{path}.method_contract_schema",
            )
        )
        return findings
    context = ValidationContext(
        base=base,
        schema_id=schema_id,
        contract=contract,
        route=route,
        run=run,
        artifacts=artifacts,
        path=path,
    )
    findings.extend(validator(context))
    return findings


def validate_workspace(path: Path) -> list[Finding]:
    base = path.resolve() if path.is_dir() else path.resolve().parent
    design = json.loads((base / "research_design.json").read_text(encoding="utf-8-sig"))
    execution = json.loads((base / "method_execution.json").read_text(encoding="utf-8-sig"))
    routes = {
        _text(item.get("id")).upper(): item
        for item in design.get("method_routes") or []
        if isinstance(item, Mapping)
    }
    findings: list[Finding] = []
    for index, run in enumerate(execution.get("runs") or []):
        if not isinstance(run, Mapping):
            continue
        route = routes.get(_text(run.get("design_id")).upper(), {})
        findings.extend(validate_run_contract(base, route, run, path=f"runs[{index}]"))
    return findings


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Workspace directory")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        findings = validate_workspace(args.path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False))
        return 2
    payload = {
        "status": "FAIL" if any(item.severity == "ERROR" for item in findings) else "PASS",
        "quality_score": None,
        "findings": [item.__dict__ for item in findings],
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Status: {payload['status']}")
        for item in findings:
            print(f"- {item.severity} {item.code}: {item.message} [{item.path}]")
    return 1 if payload["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
