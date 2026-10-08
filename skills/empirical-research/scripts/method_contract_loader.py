#!/usr/bin/env python3
"""Load and structurally validate the sole empirical-method contract registry.

This module is deliberately dependency-free so both the design controller and
the execution validator can consume the same registry and JSON Schema assets.
It is a loader/evaluator, not a second method registry and not a method-specific
validator dispatch table.  Supplemental identities resolve globally and
uniquely to one declared core id plus active revision; they are never standalone
contracts.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence


EMPIRICAL_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = EMPIRICAL_ROOT / "references" / "method-adapter-registry.json"
SUPPORTED_REGISTRY_SCHEMAS = {
    "cnki-method-adapter-registry/v1",
    "cnki-method-adapter-registry/v2",
    "cnki-method-adapter-registry/v3",
}
RESERVED_SUPPLEMENTAL_KEYS = {
    "capabilities",
    "claim_capability",
    "claim_capabilities",
    "claim_type",
    "claim_types",
    "counterfactual",
    "estimand",
    "identification_assumptions",
    "inference_ceiling",
    "method_contract_schema",
    "method_validator",
    "validator",
    "validators",
}


class ContractLoaderError(ValueError):
    """The authoritative registry or one of its registered assets is invalid."""


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractLoaderError(f"Cannot load registered JSON asset {path}: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise ContractLoaderError(f"Registered JSON asset must contain an object: {path}")
    return payload


def load_registry(path: Path = REGISTRY_PATH) -> Mapping[str, Any]:
    payload = _read_json(path)
    if payload.get("schema_version") not in SUPPORTED_REGISTRY_SCHEMAS:
        raise ContractLoaderError("Unsupported method-adapter registry schema")
    if not isinstance(payload.get("method_contracts"), Mapping):
        raise ContractLoaderError("Method-adapter registry has no method_contracts map")
    return payload


def _asset_path(value: Any) -> Path:
    relative = Path(_text(value))
    if not _text(value) or relative.is_absolute() or ".." in relative.parts:
        raise ContractLoaderError(f"Registry asset must be a repository-relative path: {value!r}")
    resolved = (EMPIRICAL_ROOT / relative).resolve()
    try:
        resolved.relative_to(EMPIRICAL_ROOT.resolve())
    except ValueError as exc:
        raise ContractLoaderError(f"Registry asset escapes empirical-research: {value!r}") from exc
    if not resolved.is_file():
        raise ContractLoaderError(f"Registered asset is missing: {resolved}")
    return resolved


def contract_spec(
    registry: Mapping[str, Any], schema_id: str
) -> tuple[Mapping[str, Any], Mapping[str, Any], Path]:
    contracts = registry.get("method_contracts")
    spec = contracts.get(schema_id) if isinstance(contracts, Mapping) else None
    if not isinstance(spec, Mapping):
        raise ContractLoaderError(f"Unknown core method contract {schema_id!r}")
    schema_path = _asset_path(spec.get("asset"))
    return spec, _read_json(schema_path), schema_path


def _recursive_reserved_paths(value: Any, path: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            child = f"{path}/{_pointer_escape(str(key))}"
            if key in RESERVED_SUPPLEMENTAL_KEYS:
                paths.append(child)
            paths.extend(_recursive_reserved_paths(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            paths.extend(_recursive_reserved_paths(item, f"{path}/{index}"))
    return paths


def supplemental_profile(
    registry: Mapping[str, Any],
    core_schema_id: str,
    core_revision: str,
    profile_id: str,
) -> tuple[Mapping[str, Any], Mapping[str, Any], Path, Mapping[str, Any], Path]:
    spec, _, _ = contract_spec(registry, core_schema_id)
    profiles = spec.get("supplemental_profiles")
    if not isinstance(profiles, list):
        profiles = []
    matches = [
        item
        for item in profiles
        if isinstance(item, Mapping) and _text(item.get("id")) == profile_id
    ]
    if len(matches) != 1:
        raise ContractLoaderError(
            f"Supplemental profile {profile_id!r} is not uniquely registered under {core_schema_id!r}"
        )
    entry = matches[0]
    allowed_entry_keys = {
        "id",
        "profile_asset",
        "schema_asset",
        "core_method_contract_id",
        "core_method_contract_revision",
    }
    extra_entry_keys = set(entry) - allowed_entry_keys
    if extra_entry_keys:
        raise ContractLoaderError(
            "Supplemental registry entry contains non-binding authority keys: "
            + ", ".join(sorted(extra_entry_keys))
        )
    if _text(entry.get("core_method_contract_id")) != core_schema_id:
        raise ContractLoaderError("Supplemental profile is bound to a different core contract")
    if _text(entry.get("core_method_contract_revision")) != _text(core_revision):
        raise ContractLoaderError("Supplemental profile is bound to a different core revision")
    if _text(spec.get("revision")) != _text(core_revision):
        raise ContractLoaderError("Selected core method-contract revision is not active")
    reserved = _recursive_reserved_paths(entry)
    if reserved:
        raise ContractLoaderError(
            "Supplemental registry entry attempts to redefine core authority at "
            + ", ".join(reserved)
        )

    profile_path = _asset_path(entry.get("profile_asset"))
    schema_path = _asset_path(entry.get("schema_asset"))
    profile = _read_json(profile_path)
    schema = _read_json(schema_path)
    if _text(profile.get("profile_id")) != profile_id:
        raise ContractLoaderError("Supplemental profile asset identity differs from the registry")
    if _text(profile.get("core_method_contract_id")) != core_schema_id:
        raise ContractLoaderError("Supplemental profile asset points to a different core contract")
    declared_schema = (profile_path.parent / _text(profile.get("profile_contract_schema"))).resolve()
    if declared_schema != schema_path:
        raise ContractLoaderError("Supplemental profile schema asset differs from the registry")
    if _text(schema.get("x-core-method-contract-id")) != core_schema_id:
        raise ContractLoaderError("Supplemental schema points to a different core contract")
    if schema.get("x-profile-contract-role") != "supplement-over-core-method-contract":
        raise ContractLoaderError("Supplemental schema does not declare its non-authoritative role")
    reserved = _recursive_reserved_paths(profile) + _recursive_reserved_paths(schema)
    if reserved:
        raise ContractLoaderError(
            "Supplemental assets attempt to redefine core method or inference authority at "
            + ", ".join(reserved)
        )
    return entry, profile, profile_path, schema, schema_path


def supplemental_profile_binding(
    registry: Mapping[str, Any],
    profile_id: str,
) -> tuple[str, str]:
    """Resolve one supplemental profile to its sole authoritative core binding.

    Callers use this before any early return for a missing core schema.  A
    supplemental selector is therefore never allowed to stand in for, or float
    independently of, the registered core method-contract id and revision.
    """

    identity = _text(profile_id)
    if not identity:
        raise ContractLoaderError("Supplemental profile identity is empty")
    contracts = registry.get("method_contracts")
    contracts = contracts if isinstance(contracts, Mapping) else {}
    matches: list[tuple[str, Mapping[str, Any], Mapping[str, Any]]] = []
    for core_id, spec in contracts.items():
        if not isinstance(spec, Mapping):
            continue
        profiles = spec.get("supplemental_profiles")
        if not isinstance(profiles, list):
            continue
        for entry in profiles:
            if isinstance(entry, Mapping) and _text(entry.get("id")) == identity:
                matches.append((_text(core_id), spec, entry))
    if len(matches) != 1:
        raise ContractLoaderError(
            f"Supplemental profile {identity!r} must map uniquely to one core method contract"
        )
    core_id, spec, entry = matches[0]
    revision = _text(spec.get("revision"))
    if _text(entry.get("core_method_contract_id")) != core_id:
        raise ContractLoaderError(
            f"Supplemental profile {identity!r} declares a different core method-contract id"
        )
    if not revision or _text(entry.get("core_method_contract_revision")) != revision:
        raise ContractLoaderError(
            f"Supplemental profile {identity!r} declares a different core method-contract revision"
        )
    # Reuse the complete registry/asset validation so this resolver cannot
    # become a weaker second interpretation of the same binding.
    supplemental_profile(registry, core_id, revision, identity)
    return core_id, revision


def _pointer_escape(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _pointer_get(document: Any, fragment: str) -> Any:
    if fragment in {"", "#"}:
        return document
    pointer = fragment[1:] if fragment.startswith("#") else fragment
    if not pointer.startswith("/"):
        raise ContractLoaderError(f"Unsupported JSON Schema fragment {fragment!r}")
    current = document
    for raw in pointer[1:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(current, Mapping) and token in current:
            current = current[token]
        else:
            raise ContractLoaderError(f"Unresolved JSON Schema fragment {fragment!r}")
    return current


def _resolve_ref(
    ref: str,
    root_schema: Mapping[str, Any],
    schema_path: Path,
) -> tuple[Mapping[str, Any], Mapping[str, Any], Path]:
    relative, marker, fragment = ref.partition("#")
    if relative:
        target_path = (schema_path.parent / relative).resolve()
        try:
            target_path.relative_to(EMPIRICAL_ROOT.resolve())
        except ValueError as exc:
            raise ContractLoaderError(f"JSON Schema reference escapes empirical-research: {ref}") from exc
        target_root = _read_json(target_path)
    else:
        target_path = schema_path
        target_root = root_schema
    target = _pointer_get(target_root, f"#{fragment}" if marker else "")
    if not isinstance(target, Mapping):
        raise ContractLoaderError(f"JSON Schema reference does not resolve to an object: {ref}")
    return target, target_root, target_path


def _type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, Mapping)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return True


def _issue(code: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "path": path or "/", "message": message}


def _schema_issues(
    value: Any,
    schema: Mapping[str, Any],
    *,
    root_schema: Mapping[str, Any],
    schema_path: Path,
    path: str,
    at_instance_root: bool,
    skip_root_required: bool,
    ref_stack: tuple[tuple[str, str], ...] = (),
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    node_code = _text(schema.get("x-error-code"))

    ref = schema.get("$ref")
    if isinstance(ref, str):
        marker = (str(schema_path), ref)
        if marker in ref_stack:
            raise ContractLoaderError(f"Recursive JSON Schema reference is unsupported: {ref}")
        target, target_root, target_path = _resolve_ref(ref, root_schema, schema_path)
        issues.extend(
            _schema_issues(
                value,
                target,
                root_schema=target_root,
                schema_path=target_path,
                path=path,
                at_instance_root=at_instance_root,
                skip_root_required=skip_root_required,
                ref_stack=ref_stack + (marker,),
            )
        )

    for member in schema.get("allOf") or []:
        if isinstance(member, Mapping):
            issues.extend(
                _schema_issues(
                    value,
                    member,
                    root_schema=root_schema,
                    schema_path=schema_path,
                    path=path,
                    at_instance_root=at_instance_root,
                    skip_root_required=skip_root_required,
                    ref_stack=ref_stack,
                )
            )

    expected = schema.get("type")
    expected_types = [expected] if isinstance(expected, str) else expected
    if isinstance(expected_types, list) and expected_types:
        if not any(_type_matches(value, item) for item in expected_types if isinstance(item, str)):
            return issues + [
                _issue(node_code or "SCHEMA.TYPE", path, f"Expected JSON type {expected!r}")
            ]
    if "const" in schema and value != schema["const"]:
        issues.append(_issue(node_code or "SCHEMA.CONST", path, "Value differs from schema const"))
    if isinstance(schema.get("enum"), list) and value not in schema["enum"]:
        issues.append(_issue(node_code or "SCHEMA.ENUM", path, "Value is not in the allowed enum"))

    if isinstance(value, str):
        if len(value) < int(schema.get("minLength", 0)):
            issues.append(_issue(node_code or "SCHEMA.MIN_LENGTH", path, "String is too short"))
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and re.search(pattern, value) is None:
            issues.append(_issue(node_code or "SCHEMA.PATTERN", path, "String does not match pattern"))
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        minimum = schema.get("minimum")
        if isinstance(minimum, (int, float)) and value < minimum:
            issues.append(_issue(node_code or "SCHEMA.MINIMUM", path, "Number is below minimum"))
    elif isinstance(value, list):
        if len(value) < int(schema.get("minItems", 0)):
            issues.append(_issue(node_code or "SCHEMA.MIN_ITEMS", path, "Array has too few items"))
        if schema.get("uniqueItems"):
            frozen = [json.dumps(item, ensure_ascii=False, sort_keys=True) for item in value]
            if len(frozen) != len(set(frozen)):
                issues.append(_issue(node_code or "SCHEMA.UNIQUE_ITEMS", path, "Array items are not unique"))
        item_schema = schema.get("items")
        if isinstance(item_schema, Mapping):
            for index, item in enumerate(value):
                issues.extend(
                    _schema_issues(
                        item,
                        item_schema,
                        root_schema=root_schema,
                        schema_path=schema_path,
                        path=f"{path}/{index}",
                        at_instance_root=False,
                        skip_root_required=skip_root_required,
                        ref_stack=ref_stack,
                    )
                )
    elif isinstance(value, Mapping):
        properties = schema.get("properties")
        properties = properties if isinstance(properties, Mapping) else {}
        if not (at_instance_root and skip_root_required):
            for key in schema.get("required") or []:
                if key not in value:
                    property_schema = properties.get(key)
                    property_code = (
                        _text(property_schema.get("x-error-code"))
                        if isinstance(property_schema, Mapping)
                        else ""
                    )
                    issues.append(
                        _issue(
                            property_code or node_code or "SCHEMA.REQUIRED",
                            f"{path}/{_pointer_escape(str(key))}",
                            f"Required property {key!r} is missing",
                        )
                    )
        for key, item in value.items():
            property_schema = properties.get(key)
            if isinstance(property_schema, Mapping):
                issues.extend(
                    _schema_issues(
                        item,
                        property_schema,
                        root_schema=root_schema,
                        schema_path=schema_path,
                        path=f"{path}/{_pointer_escape(str(key))}",
                        at_instance_root=False,
                        skip_root_required=skip_root_required,
                        ref_stack=ref_stack,
                    )
                )
            elif schema.get("additionalProperties") is False:
                issues.append(
                    _issue(
                        node_code or "SCHEMA.ADDITIONAL_PROPERTY",
                        f"{path}/{_pointer_escape(str(key))}",
                        f"Additional property {key!r} is forbidden",
                    )
                )
    return issues


def validate_schema(
    value: Any,
    schema: Mapping[str, Any],
    schema_path: Path,
    *,
    root_required: Sequence[str] | None = None,
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if root_required is not None:
        if not isinstance(value, Mapping):
            return [_issue("SCHEMA.TYPE", "/", "Method contract must be an object")]
        properties = schema.get("properties")
        properties = properties if isinstance(properties, Mapping) else {}
        for key in root_required:
            if key not in value:
                property_schema = properties.get(key)
                property_code = (
                    _text(property_schema.get("x-error-code"))
                    if isinstance(property_schema, Mapping)
                    else ""
                )
                issues.append(
                    _issue(
                        property_code or "SCHEMA.REQUIRED",
                        f"/{_pointer_escape(str(key))}",
                        f"Design-required property {key!r} is missing",
                    )
                )
    issues.extend(
        _schema_issues(
            value,
            schema,
            root_schema=schema,
            schema_path=schema_path,
            path="",
            at_instance_root=True,
            skip_root_required=root_required is not None,
        )
    )
    unique: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in issues:
        marker = (item["code"], item["path"], item["message"])
        if marker not in seen:
            seen.add(marker)
            unique.append(item)
    return unique


def validate_core_contract(
    registry: Mapping[str, Any],
    schema_id: str,
    contract: Any,
    *,
    phase: str,
) -> list[dict[str, str]]:
    spec, schema, schema_path = contract_spec(registry, schema_id)
    if phase not in {"design", "execution"}:
        raise ContractLoaderError(f"Unsupported method-contract phase {phase!r}")
    required = spec.get("design_required") if phase == "design" else None
    root_required = list(required or []) if phase == "design" else None
    return validate_schema(contract, schema, schema_path, root_required=root_required)


def validate_supplemental_contract(
    registry: Mapping[str, Any],
    core_schema_id: str,
    core_revision: str,
    profile_id: str,
    contract: Any,
) -> tuple[list[dict[str, str]], set[str]]:
    bound_core_id, bound_revision = supplemental_profile_binding(registry, profile_id)
    if core_schema_id != bound_core_id or _text(core_revision) != bound_revision:
        raise ContractLoaderError(
            f"Supplemental profile {profile_id!r} requires core "
            f"{bound_core_id!r} revision {bound_revision!r}"
        )
    _, _, _, schema, schema_path = supplemental_profile(
        registry,
        core_schema_id,
        core_revision,
        profile_id,
    )
    issues = validate_schema(contract, schema, schema_path)
    for reserved_path in _recursive_reserved_paths(contract):
        issues.append(
            _issue(
                "SUPPLEMENTAL.RESERVED_AUTHORITY",
                reserved_path,
            "Supplemental contract cannot redefine core method or inference authority; use *_ref fields",
            )
        )
    return issues, artifact_ids(contract, schema, schema_path)


def artifact_ids(value: Any, schema: Mapping[str, Any], schema_path: Path) -> set[str]:
    """Collect Artifact IDs only from schema-declared supplemental artifact slots."""
    found: set[str] = set()

    def walk(
        item: Any,
        node: Mapping[str, Any],
        root: Mapping[str, Any],
        current_path: Path,
        stack: tuple[tuple[str, str], ...] = (),
    ) -> None:
        ref = node.get("$ref")
        if isinstance(ref, str):
            marker = (str(current_path), ref)
            if marker in stack:
                return
            target, target_root, target_path = _resolve_ref(ref, root, current_path)
            if target.get("x-error-code") == "PTP.ARTIFACT.ID" and isinstance(item, str):
                found.add(item.upper())
            walk(item, target, target_root, target_path, stack + (marker,))
        for member in node.get("allOf") or []:
            if isinstance(member, Mapping):
                walk(item, member, root, current_path, stack)
        if isinstance(item, Mapping):
            properties = node.get("properties")
            if isinstance(properties, Mapping):
                for key, child in item.items():
                    child_schema = properties.get(key)
                    if isinstance(child_schema, Mapping):
                        walk(child, child_schema, root, current_path, stack)
        elif isinstance(item, list) and isinstance(node.get("items"), Mapping):
            for child in item:
                walk(child, node["items"], root, current_path, stack)

    walk(value, schema, schema, schema_path)
    return found
