#!/usr/bin/env python3
"""Compute cumulative L0-L5 method maturity from the sole method registry."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = Path(
    "skills/empirical-research/references/method-adapter-registry.json"
)
METHOD_ROOT = Path("skills/empirical-research")
EXPECTED_REGISTRY_SCHEMA = "cnki-method-adapter-registry/v3"
EXPECTED_PROFILE_SCHEMA = "method-operation/v1"
VALID_SUPPORT_STATUSES = {"experimental_method_support", "production_ready"}


@dataclass(frozen=True)
class MethodMaturity:
    family: str
    level: int
    declared_support_status: str
    profile_asset: str | None
    blocked_by: tuple[str, ...]

    @property
    def label(self) -> str:
        return f"L{self.level}"


@dataclass(frozen=True)
class MaturityReport:
    issues: tuple[str, ...]
    methods: tuple[MethodMaturity, ...]

    @property
    def passed(self) -> bool:
        return not self.issues

    @property
    def levels(self) -> Mapping[int, int]:
        return Counter(item.level for item in self.methods)


def _is_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _string_list(value: Any, *, minimum: int = 0) -> bool:
    return (
        isinstance(value, list)
        and len(value) >= minimum
        and all(_is_text(item) for item in value)
        and len(value) == len(set(value))
    )


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _repo_file(root: Path, raw: Any) -> Path | None:
    if not _is_text(raw):
        return None
    relative = Path(raw)
    if relative.is_absolute():
        return None
    root_resolved = root.resolve()
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError:
        return None
    return resolved if resolved.is_file() else None


def _method_file(root: Path, raw: Any) -> Path | None:
    if not _is_text(raw):
        return None
    return _repo_file(root, (METHOD_ROOT / str(raw)).as_posix())


def _read_mapping(path: Path | None, label: str, issues: list[str]) -> Mapping[str, Any] | None:
    if path is None:
        issues.append(f"{label} does not resolve to a repository file")
        return None
    try:
        value = _load_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        issues.append(f"cannot read {label}: {exc}")
        return None
    if not isinstance(value, Mapping):
        issues.append(f"{label} must contain a JSON object")
        return None
    return value


def _profile_shape_issues(
    profile: Mapping[str, Any],
    family: str,
    root: Path,
    taxonomy: Mapping[str, Any],
) -> list[str]:
    prefix = f"family {family!r} operation profile"
    issues: list[str] = []
    if profile.get("schema_version") != EXPECTED_PROFILE_SCHEMA:
        issues.append(f"{prefix} schema_version must equal {EXPECTED_PROFILE_SCHEMA!r}")
    if profile.get("family") != family:
        issues.append(f"{prefix} identifies family {profile.get('family')!r}")

    required_operations = profile.get("required_operation_kinds")
    if not _string_list(required_operations, minimum=1):
        issues.append(f"{prefix} required_operation_kinds must be unique non-empty strings")
        required_operations = []
    optional_operations = profile.get("optional_operation_kinds", [])
    if not _string_list(optional_operations):
        issues.append(f"{prefix} optional_operation_kinds must be unique strings")
        optional_operations = []
    if set(required_operations) & set(optional_operations):
        issues.append(f"{prefix} repeats required operations as optional")

    artifacts = profile.get("required_artifact_roles")
    if not _string_list(artifacts, minimum=1):
        issues.append(f"{prefix} required_artifact_roles must be unique non-empty strings")

    mvmr = profile.get("minimum_viable_run")
    if not isinstance(mvmr, Mapping):
        issues.append(f"{prefix} minimum_viable_run must be an object")
    else:
        if not _is_text(mvmr.get("profile_id")):
            issues.append(f"{prefix} minimum_viable_run.profile_id must be non-empty")
        pilot_operations = mvmr.get("required_operation_kinds")
        if not _string_list(pilot_operations, minimum=1):
            issues.append(
                f"{prefix} minimum_viable_run.required_operation_kinds must be unique strings"
            )
            pilot_operations = []
        unknown = sorted(set(pilot_operations) - set(required_operations))
        if unknown:
            issues.append(
                f"{prefix} minimum_viable_run uses undeclared operations: {', '.join(unknown)}"
            )
        if not _string_list(mvmr.get("acceptance_dimensions"), minimum=1):
            issues.append(
                f"{prefix} minimum_viable_run.acceptance_dimensions must be unique strings"
            )

    if not _string_list(profile.get("completion_predicates"), minimum=1):
        issues.append(f"{prefix} completion_predicates must be unique non-empty strings")
    if not _string_list(profile.get("judgment_nodes"), minimum=1):
        issues.append(f"{prefix} judgment_nodes must be unique non-empty strings")

    namespaces = taxonomy.get("namespaces")
    route_patterns = taxonomy.get("route_patterns")
    known_namespaces = set(namespaces) if isinstance(namespaces, Mapping) else set()
    known_routes = set(route_patterns) if _string_list(route_patterns, minimum=1) else set()
    failure_routes = profile.get("failure_routes")
    if not isinstance(failure_routes, list) or not failure_routes:
        issues.append(f"{prefix} failure_routes must be a non-empty array")
    else:
        codes: set[str] = set()
        for index, failure in enumerate(failure_routes):
            if not isinstance(failure, Mapping):
                issues.append(f"{prefix} failure_routes[{index}] must be an object")
                continue
            code = failure.get("code")
            route = failure.get("route")
            if not _is_text(code) or "." not in str(code):
                issues.append(f"{prefix} failure_routes[{index}].code must be namespaced")
            else:
                namespace = str(code).split(".", 1)[0]
                if namespace not in known_namespaces:
                    issues.append(f"{prefix} uses unknown failure namespace {namespace!r}")
                if code in codes:
                    issues.append(f"{prefix} repeats failure code {code!r}")
                codes.add(str(code))
            if route not in known_routes:
                issues.append(f"{prefix} uses undeclared failure route {route!r}")

    evidence = profile.get("maturity_evidence")
    if not isinstance(evidence, Mapping):
        issues.append(f"{prefix} maturity_evidence must be an object")
    else:
        validator = evidence.get("validator")
        if not _is_text(validator) or _repo_file(root, validator) is None:
            issues.append(f"{prefix} maturity_evidence.validator must resolve to a file")
        for field in ("positive_case", "negative_case", "worked_example"):
            value = evidence.get(field)
            if value is not None and not isinstance(value, Mapping):
                issues.append(f"{prefix} maturity_evidence.{field} must be an object or null")
        end_to_end = evidence.get("end_to_end_eval")
        if end_to_end is not None and not _is_text(end_to_end):
            issues.append(
                f"{prefix} maturity_evidence.end_to_end_eval must be a path or null"
            )
    return issues


def _native_contract_is_real(
    root: Path,
    family: str,
    specification: Mapping[str, Any],
    contracts: Mapping[str, Any],
) -> bool:
    """Require an explicitly registered contract whose namespace names the family."""

    expected_namespace = family.replace("_", "-")
    profiles = specification.get("method_contract_profiles")
    if not _string_list(profiles, minimum=1):
        return False
    for profile_id in profiles:
        if str(profile_id).split("/", 1)[0] != expected_namespace:
            continue
        contract = contracts.get(profile_id)
        if not isinstance(contract, Mapping):
            continue
        if not _string_list(contract.get("design_required"), minimum=1):
            continue
        schema_path = _method_file(root, contract.get("asset"))
        validator_name = contract.get("validator")
        validator_path = (
            root
            / METHOD_ROOT
            / "scripts"
            / "validators"
            / f"{validator_name}.py"
        )
        if schema_path is None or not _is_text(validator_name) or not validator_path.is_file():
            continue
        try:
            schema = _load_json(schema_path)
        except (OSError, json.JSONDecodeError):
            continue
        if (
            isinstance(schema, Mapping)
            and schema.get("type") == "object"
            and _string_list(schema.get("required"), minimum=1)
        ):
            return True
    return False


def _real_evidence_asset(root: Path, value: Any) -> bool:
    return isinstance(value, Mapping) and _repo_file(root, value.get("asset")) is not None


def _level_four_evidence_is_real(root: Path, profile: Mapping[str, Any]) -> bool:
    mvmr = profile.get("minimum_viable_run")
    evidence = profile.get("maturity_evidence")
    return (
        isinstance(mvmr, Mapping)
        and _string_list(mvmr.get("required_operation_kinds"), minimum=1)
        and _string_list(mvmr.get("acceptance_dimensions"), minimum=1)
        and isinstance(evidence, Mapping)
        and all(
            _real_evidence_asset(root, evidence.get(field))
            for field in ("positive_case", "negative_case", "worked_example")
        )
    )


def _level_five_evidence_is_real(root: Path, profile: Mapping[str, Any]) -> bool:
    evidence = profile.get("maturity_evidence")
    return isinstance(evidence, Mapping) and _repo_file(
        root, evidence.get("end_to_end_eval")
    ) is not None


def validate_maturity(
    root: Path,
    registry: Mapping[str, Any],
    *,
    profile_overrides: Mapping[str, Mapping[str, Any]] | None = None,
) -> MaturityReport:
    """Validate registry-indexed assets and conservatively compute cumulative maturity."""

    root = root.resolve()
    issues: list[str] = []
    methods: list[MethodMaturity] = []
    if registry.get("schema_version") != EXPECTED_REGISTRY_SCHEMA:
        issues.append(
            f"registry.schema_version must equal {EXPECTED_REGISTRY_SCHEMA!r}"
        )
    if registry.get("registry_version") != "5.1.0":
        issues.append("registry.registry_version must equal '5.1.0'")

    schema = _read_mapping(
        _method_file(root, registry.get("operation_profile_schema_asset")),
        "registry.operation_profile_schema_asset",
        issues,
    )
    if schema is not None and schema.get("properties", {}).get("schema_version", {}).get(
        "const"
    ) != EXPECTED_PROFILE_SCHEMA:
        issues.append("operation profile schema does not declare method-operation/v1")
    taxonomy = _read_mapping(
        _method_file(root, registry.get("failure_taxonomy_asset")),
        "registry.failure_taxonomy_asset",
        issues,
    )
    if taxonomy is None:
        taxonomy = {}

    families = registry.get("families")
    contracts = registry.get("method_contracts")
    if not isinstance(families, Mapping):
        return MaturityReport(("registry.families must be an object",), ())
    if not isinstance(contracts, Mapping):
        issues.append("registry.method_contracts must be an object")
        contracts = {}

    seen_assets: dict[str, str] = {}
    operation_signatures: dict[tuple[str, ...], str] = {}
    artifact_signatures: dict[tuple[str, ...], str] = {}
    overrides = profile_overrides or {}
    for family, raw_specification in sorted(families.items()):
        if not _is_text(family) or not isinstance(raw_specification, Mapping):
            issues.append(f"invalid registry family entry: {family!r}")
            continue
        if raw_specification.get("migration_only") is True:
            continue
        specification = raw_specification
        level = 0
        blocked_by: list[str] = []
        if _string_list(specification.get("design_fields"), minimum=1):
            level = 1
        else:
            blocked_by.append("structured_design_fields")

        native_contract = _native_contract_is_real(
            root, family, specification, contracts
        )
        if level == 1 and native_contract:
            level = 2
        elif level == 1:
            blocked_by.append("typed_contract")

        profile_asset = specification.get("operation_profile_asset")
        profile_asset_text = str(profile_asset) if _is_text(profile_asset) else None
        if profile_asset_text is None:
            issues.append(f"family {family!r} lacks operation_profile_asset")
            profile: Mapping[str, Any] | None = None
        else:
            previous = seen_assets.get(profile_asset_text)
            if previous is not None:
                issues.append(
                    f"families {previous!r} and {family!r} share operation profile asset {profile_asset_text!r}"
                )
            seen_assets[profile_asset_text] = family
            if family in overrides:
                profile = overrides[family]
            else:
                profile = _read_mapping(
                    _method_file(root, profile_asset_text),
                    f"family {family!r} operation_profile_asset",
                    issues,
                )

        profile_valid = False
        if profile is not None:
            profile_issues = _profile_shape_issues(profile, family, root, taxonomy)
            issues.extend(profile_issues)
            profile_valid = not profile_issues
            operation_signature = tuple(sorted(profile.get("required_operation_kinds", [])))
            artifact_signature = tuple(sorted(profile.get("required_artifact_roles", [])))
            if operation_signature:
                previous = operation_signatures.get(operation_signature)
                if previous is not None:
                    issues.append(
                        f"families {previous!r} and {family!r} have identical required operation signatures"
                    )
                operation_signatures[operation_signature] = family
            if artifact_signature:
                previous = artifact_signatures.get(artifact_signature)
                if previous is not None:
                    issues.append(
                        f"families {previous!r} and {family!r} have identical artifact-role signatures"
                    )
                artifact_signatures[artifact_signature] = family

        if level == 2 and profile_valid:
            level = 3
        elif level == 2:
            blocked_by.append("operation_profile")

        if level == 3 and profile is not None and _level_four_evidence_is_real(root, profile):
            level = 4
        elif level == 3:
            blocked_by.append("mvmr_examples")

        if level == 4 and profile is not None and _level_five_evidence_is_real(root, profile):
            level = 5
        elif level == 4:
            blocked_by.append("end_to_end_eval")

        status = specification.get("declared_support_status")
        if status not in VALID_SUPPORT_STATUSES:
            issues.append(
                f"family {family!r} declared_support_status must be one of "
                + ", ".join(sorted(VALID_SUPPORT_STATUSES))
            )
            status_text = str(status)
        else:
            status_text = str(status)
        if status == "production_ready" and level < 4:
            issues.append(
                f"family {family!r} declares production_ready but computes to L{level}; L4 is required"
            )
        methods.append(
            MethodMaturity(
                family=family,
                level=level,
                declared_support_status=status_text,
                profile_asset=profile_asset_text,
                blocked_by=tuple(blocked_by),
            )
        )

    return MaturityReport(tuple(issues), tuple(methods))


def check(
    root: Path = ROOT,
    registry_path: Path = DEFAULT_REGISTRY,
) -> MaturityReport:
    root = root.resolve()
    resolved = registry_path if registry_path.is_absolute() else root / registry_path
    try:
        registry = _load_json(resolved)
    except (OSError, json.JSONDecodeError) as exc:
        return MaturityReport((f"cannot read method registry: {exc}",), ())
    if not isinstance(registry, Mapping):
        return MaturityReport(("method registry root must be an object",), ())
    return validate_maturity(root, registry)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", required=True)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    args = parser.parse_args()
    report = check(args.root, args.registry)
    if report.issues:
        print("Method maturity check: FAIL")
        for issue in report.issues:
            print(f"- {issue}")
        return 1
    distribution = ", ".join(
        f"L{level}={count}" for level, count in sorted(report.levels.items())
    )
    experimental = sum(
        item.declared_support_status == "experimental_method_support"
        for item in report.methods
    )
    print(
        "Method maturity check: PASS "
        f"({len(report.methods)} families; {distribution}; {experimental} experimental)"
    )
    for item in report.methods:
        blockers = ",".join(item.blocked_by) if item.blocked_by else "none"
        print(
            f"- {item.family}: {item.label}; "
            f"status={item.declared_support_status}; blocked_by={blockers}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
