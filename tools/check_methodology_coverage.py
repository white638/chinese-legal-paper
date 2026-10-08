#!/usr/bin/env python3
"""Fail closed when executable method families lack semantic eval coverage."""

from __future__ import annotations

import argparse
import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = Path(
    "skills/empirical-research/references/method-adapter-registry.json"
)
DEFAULT_CASES = Path("evals/methodology-routing/cases.json")
MANIFEST_SCHEMA = "avereth-methodology-routing-cases/v2"
REQUIRED_ROLES = {
    "positive",
    "error",
    "boundary",
    "inference-overreach",
}
CAPABILITY_ERROR = "ME.INFERENCE.CAPABILITY_EXCEEDED"
CORE_CONTRACT_COVERAGE_MODULE = Path(
    "skills/empirical-research/scripts/test_method_artifacts.py"
)
CORE_CONTRACT_COVERAGE_NAME = "CORE_CONTRACTS_UNDER_EXECUTABLE_TEST"
FAMILY_SEMANTIC_RULES_MODULE = Path(
    "skills/empirical-research/scripts/method_execution.py"
)
FAMILY_SEMANTIC_RULES_NAME = "FAMILY_SEMANTIC_RULES"


@dataclass(frozen=True)
class CoverageReport:
    issues: tuple[str, ...]
    executable_families: tuple[str, ...]
    instantiated_case_count: int

    @property
    def passed(self) -> bool:
        return not self.issues


def _is_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _declared_core_contract_coverage(root: Path, issues: list[str]) -> tuple[str, ...]:
    module_path = _repo_file(
        root,
        CORE_CONTRACT_COVERAGE_MODULE.as_posix(),
        "core_contract_coverage.module",
        issues,
    )
    if module_path is None:
        return ()
    try:
        tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    except (OSError, SyntaxError) as exc:
        issues.append(f"cannot parse core contract coverage module: {exc}")
        return ()
    declarations: list[Any] = []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(
            isinstance(target, ast.Name) and target.id == CORE_CONTRACT_COVERAGE_NAME
            for target in node.targets
        ):
            try:
                declarations.append(ast.literal_eval(node.value))
            except (ValueError, SyntaxError):
                issues.append(
                    f"{CORE_CONTRACT_COVERAGE_NAME} must be a literal string collection"
                )
                return ()
    if len(declarations) != 1:
        issues.append(
            f"coverage module must declare {CORE_CONTRACT_COVERAGE_NAME} exactly once"
        )
        return ()
    declared = declarations[0]
    if not isinstance(declared, (tuple, list, set)) or not all(
        _is_text(item) for item in declared
    ):
        issues.append(f"{CORE_CONTRACT_COVERAGE_NAME} must contain only non-empty strings")
        return ()
    if len(declared) != len(set(declared)):
        issues.append(f"{CORE_CONTRACT_COVERAGE_NAME} contains duplicate contract IDs")
    return tuple(str(item) for item in declared)


def _declared_family_semantic_rules(
    root: Path,
    issues: list[str],
) -> dict[str, dict[str, Mapping[str, Any]]]:
    """Read the literal runtime rule declaration without importing validator code."""

    module_path = _repo_file(
        root,
        FAMILY_SEMANTIC_RULES_MODULE.as_posix(),
        "family_semantic_rules.module",
        issues,
    )
    if module_path is None:
        return {}
    try:
        tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    except (OSError, SyntaxError) as exc:
        issues.append(f"cannot parse family semantic rules module: {exc}")
        return {}
    declarations: list[Any] = []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(
            isinstance(target, ast.Name) and target.id == FAMILY_SEMANTIC_RULES_NAME
            for target in node.targets
        ):
            try:
                declarations.append(ast.literal_eval(node.value))
            except (ValueError, SyntaxError):
                issues.append(f"{FAMILY_SEMANTIC_RULES_NAME} must be a literal mapping")
                return {}
    if len(declarations) != 1:
        issues.append(
            f"family semantic validator must declare {FAMILY_SEMANTIC_RULES_NAME} exactly once"
        )
        return {}
    raw = declarations[0]
    if not isinstance(raw, Mapping):
        issues.append(f"{FAMILY_SEMANTIC_RULES_NAME} must be a mapping")
        return {}
    parsed: dict[str, dict[str, Mapping[str, Any]]] = {}
    for family, rules in raw.items():
        if not _is_text(family) or not isinstance(rules, (tuple, list)):
            issues.append(f"invalid family semantic rule collection for {family!r}")
            continue
        by_code: dict[str, Mapping[str, Any]] = {}
        ids: set[str] = set()
        for index, rule in enumerate(rules):
            if not isinstance(rule, Mapping):
                issues.append(f"family semantic rule {family!r}[{index}] must be an object")
                continue
            rule_id = rule.get("id")
            field = rule.get("field")
            code = rule.get("code")
            needles = rule.get("contains_all")
            if not all(_is_text(item) for item in (rule_id, field, code, rule.get("message"))):
                issues.append(f"family semantic rule {family!r}[{index}] is incomplete")
                continue
            if not isinstance(needles, (tuple, list)) or not needles or not all(
                _is_text(item) for item in needles
            ):
                issues.append(
                    f"family semantic rule {family!r}/{rule_id!r} needs contains_all tokens"
                )
                continue
            if rule_id in ids:
                issues.append(f"duplicate family semantic rule id for {family!r}: {rule_id}")
            if code in by_code:
                issues.append(f"duplicate family semantic validator code for {family!r}: {code}")
            ids.add(str(rule_id))
            by_code[str(code)] = rule
        parsed[str(family)] = by_code
    return parsed


def _repo_file(root: Path, raw: Any, field: str, issues: list[str]) -> Path | None:
    if not _is_text(raw):
        issues.append(f"{field} must be a non-empty repository-relative path")
        return None
    relative = Path(raw)
    if relative.is_absolute():
        issues.append(f"{field} must be repository-relative: {raw}")
        return None
    root_resolved = root.resolve()
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError:
        issues.append(f"{field} escapes the repository: {raw}")
        return None
    if not resolved.is_file():
        issues.append(f"{field} does not exist: {raw}")
        return None
    return resolved


def _executable_families(registry: Mapping[str, Any], issues: list[str]) -> tuple[str, ...]:
    families = registry.get("families")
    if not isinstance(families, Mapping):
        issues.append("registry.families must be an object")
        return ()
    executable: list[str] = []
    for family, specification in sorted(families.items()):
        if not _is_text(family) or not isinstance(specification, Mapping):
            issues.append(f"registry family entry is invalid: {family!r}")
            continue
        if specification.get("migration_only") is True:
            continue
        if not isinstance(specification.get("execution_fields"), list):
            issues.append(f"registry family {family!r} lacks an execution_fields array")
        executable.append(family)
    return tuple(executable)


def validate_coverage(
    root: Path,
    registry: Mapping[str, Any],
    manifest: Mapping[str, Any],
    *,
    registry_relative_path: Path = DEFAULT_REGISTRY,
) -> CoverageReport:
    """Validate registry-to-case coverage without running the case harness."""

    issues: list[str] = []
    executable = _executable_families(registry, issues)
    family_semantic_rules = _declared_family_semantic_rules(root, issues)
    contracts = registry.get("method_contracts")
    if not isinstance(contracts, Mapping) or not contracts:
        issues.append("registry.method_contracts must be a non-empty object")
        contracts = {}
    declared_contracts = set(_declared_core_contract_coverage(root, issues))
    registered_contracts = set(contracts)
    for profile in sorted(registered_contracts - declared_contracts):
        issues.append(
            f"typed method profile lacks structured executable coverage: {profile}"
        )
    for profile in sorted(declared_contracts - registered_contracts):
        issues.append(
            f"structured executable coverage names an unknown typed method profile: {profile}"
        )
    referenced_profiles: dict[str, set[str]] = {}
    families_value = registry.get("families") if isinstance(registry.get("families"), Mapping) else {}
    for family, specification in families_value.items():
        if not isinstance(specification, Mapping):
            continue
        for profile in specification.get("method_contract_profiles") or []:
            referenced_profiles.setdefault(str(profile), set()).add(str(family))
    for profile, specification in sorted(contracts.items()):
        if not _is_text(profile) or not isinstance(specification, Mapping):
            issues.append(f"typed method profile entry is invalid: {profile!r}")
            continue
        asset = _repo_file(
            root,
            (Path("skills/empirical-research") / str(specification.get("asset", ""))).as_posix(),
            f"method_contracts.{profile}.asset",
            issues,
        )
        if asset is not None:
            try:
                schema = _load_json(asset)
            except (OSError, json.JSONDecodeError) as exc:
                issues.append(f"typed method profile {profile!r} has invalid JSON schema: {exc}")
            else:
                if not isinstance(schema, Mapping) or (
                    schema.get("type") != "object" and not isinstance(schema.get("allOf"), list)
                ):
                    issues.append(f"typed method profile {profile!r} schema must describe an object")
        validator = specification.get("validator")
        validator_path = root / "skills" / "empirical-research" / "scripts" / "validators" / f"{validator}.py"
        if not _is_text(validator) or not validator_path.is_file():
            issues.append(f"typed method profile {profile!r} lacks a registered validator module")
        if not _is_text(specification.get("revision")):
            issues.append(f"typed method profile {profile!r} lacks a contract revision")
        if profile not in referenced_profiles:
            issues.append(f"typed method profile is not mapped to an executable family: {profile}")
    for profile in sorted(set(referenced_profiles) - set(contracts)):
        issues.append(f"family maps an unknown typed method profile: {profile}")
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        issues.append(
            "manifest.schema_version must equal "
            f"{MANIFEST_SCHEMA!r}, got {manifest.get('schema_version')!r}"
        )

    registry_contract = manifest.get("registry")
    if not isinstance(registry_contract, Mapping):
        issues.append("manifest.registry must be an object")
        registry_contract = {}
    declared_path = registry_contract.get("path")
    if declared_path != registry_relative_path.as_posix():
        issues.append(
            "manifest.registry.path does not identify the checked registry: "
            f"{declared_path!r}"
        )
    for field in ("schema_version", "registry_version"):
        if registry_contract.get(field) != registry.get(field):
            issues.append(
                f"manifest.registry.{field} drifted: declared "
                f"{registry_contract.get(field)!r}, registry has {registry.get(field)!r}"
            )

    capabilities = registry.get("claim_capabilities")
    if not isinstance(capabilities, Mapping):
        issues.append("registry.claim_capabilities must be an object")
        capabilities = {}
    known_claim_types: set[str] = set()
    for family in executable:
        allowed = capabilities.get(family)
        if not isinstance(allowed, list) or not allowed or not all(_is_text(item) for item in allowed):
            issues.append(f"registry claim capabilities missing for executable family {family!r}")
            continue
        known_claim_types.update(allowed)

    harnesses = manifest.get("harnesses")
    if not isinstance(harnesses, Mapping) or not harnesses:
        issues.append("manifest.harnesses must be a non-empty object")
        harnesses = {}
    for harness_id, harness in harnesses.items():
        if not isinstance(harness, Mapping):
            issues.append(f"harness {harness_id!r} must be an object")
            continue
        _repo_file(root, harness.get("path"), f"harnesses.{harness_id}.path", issues)
        test_ids = harness.get("test_ids")
        if not isinstance(test_ids, list) or not test_ids or not all(
            _is_text(item) for item in test_ids
        ):
            issues.append(f"harnesses.{harness_id}.test_ids must be a non-empty string array")
        elif len(test_ids) != len(set(test_ids)):
            issues.append(f"harnesses.{harness_id}.test_ids contains duplicates")

    source_manifests = manifest.get("source_manifests")
    if not isinstance(source_manifests, Mapping) or not source_manifests:
        issues.append("manifest.source_manifests must be a non-empty object")
        source_manifests = {}
    source_variants: dict[str, set[str]] = {}
    for source_id, source in source_manifests.items():
        if not isinstance(source, Mapping):
            issues.append(f"source manifest {source_id!r} must be an object")
            continue
        source_path = _repo_file(
            root,
            source.get("path"),
            f"source_manifests.{source_id}.path",
            issues,
        )
        variants_field = source.get("variants_field")
        if not _is_text(variants_field):
            issues.append(f"source_manifests.{source_id}.variants_field must be non-empty")
            continue
        if source_path is None:
            continue
        try:
            source_payload = _load_json(source_path)
        except (OSError, json.JSONDecodeError) as exc:
            issues.append(f"cannot read source manifest {source_id!r}: {exc}")
            continue
        variants = source_payload.get(variants_field) if isinstance(source_payload, Mapping) else None
        if not isinstance(variants, list) or not all(_is_text(item) for item in variants):
            issues.append(
                f"source manifest {source_id!r} field {variants_field!r} must be a string array"
            )
            continue
        source_variants[source_id] = set(variants)

    contract = manifest.get("coverage_contract")
    if not isinstance(contract, Mapping):
        issues.append("manifest.coverage_contract must be an object")
        contract = {}
    declared_roles = contract.get("required_roles")
    if not isinstance(declared_roles, list) or set(declared_roles) != REQUIRED_ROLES:
        issues.append(
            "coverage_contract.required_roles must contain exactly "
            + ", ".join(sorted(REQUIRED_ROLES))
        )
    minimum_family_errors = contract.get("minimum_family_specific_error_cases")
    if (
        not isinstance(minimum_family_errors, int)
        or isinstance(minimum_family_errors, bool)
        or minimum_family_errors < 2
    ):
        issues.append(
            "coverage_contract.minimum_family_specific_error_cases must be an integer >= 2"
        )
        minimum_family_errors = 2
    if contract.get("generic_error_templates_count_toward_minimum") is not False:
        issues.append(
            "coverage_contract.generic_error_templates_count_toward_minimum must be false"
        )
    if contract.get("family_error_distinctness") != [
        "failure_mode",
        "typed_mutation",
        "expected_error_codes",
    ]:
        issues.append("coverage_contract.family_error_distinctness drifted")
    semantic_declaration = contract.get("family_semantic_rules")
    if semantic_declaration != {
        "path": FAMILY_SEMANTIC_RULES_MODULE.as_posix(),
        "constant": FAMILY_SEMANTIC_RULES_NAME,
    }:
        issues.append(
            "coverage_contract.family_semantic_rules must identify the executable runtime declaration"
        )

    templates_raw = manifest.get("case_templates")
    if not isinstance(templates_raw, list) or not templates_raw:
        issues.append("manifest.case_templates must be a non-empty array")
        templates_raw = []
    templates: dict[str, Mapping[str, Any]] = {}
    for index, template in enumerate(templates_raw):
        prefix = f"case_templates[{index}]"
        if not isinstance(template, Mapping):
            issues.append(f"{prefix} must be an object")
            continue
        template_id = template.get("id")
        if not _is_text(template_id):
            issues.append(f"{prefix}.id must be non-empty")
            continue
        if template_id in templates:
            issues.append(f"duplicate case template id: {template_id}")
            continue
        templates[template_id] = template
        role = template.get("role")
        if role not in REQUIRED_ROLES:
            issues.append(f"template {template_id!r} has unsupported role {role!r}")
        harness = template.get("harness")
        if harness not in harnesses:
            issues.append(f"template {template_id!r} references unknown harness {harness!r}")
        source_id = template.get("source_manifest")
        source_variant = template.get("source_variant")
        if source_id not in source_manifests:
            issues.append(
                f"template {template_id!r} references unknown source manifest {source_id!r}"
            )
        elif source_variant not in source_variants.get(source_id, set()):
            issues.append(
                f"template {template_id!r} source variant {source_variant!r} is not declared "
                f"by {source_id!r}"
            )
        mutation = template.get("mutation")
        if not isinstance(mutation, Mapping) or not _is_text(mutation.get("operator")):
            issues.append(f"template {template_id!r} must declare a typed mutation.operator")
            mutation = {}
        expected = template.get("expected")
        if not isinstance(expected, Mapping):
            issues.append(f"template {template_id!r}.expected must be an object")
            expected = {}
        status = expected.get("status")
        codes = expected.get("codes")
        if status not in {"PASS", "FAIL"}:
            issues.append(f"template {template_id!r} expected.status must be PASS or FAIL")
        if not isinstance(codes, list) or not all(_is_text(code) for code in codes):
            issues.append(f"template {template_id!r} expected.codes must be a string array")
            codes = []
        if role == "positive" and (
            mutation.get("operator") != "none" or status != "PASS" or codes
        ):
            issues.append(
                f"positive template {template_id!r} must be an unmutated PASS with no error codes"
            )
        if role == "error" and (
            status != "FAIL" or not codes or not _is_text(template.get("failure_mode"))
        ):
            issues.append(
                f"error template {template_id!r} needs a failure_mode and expected FAIL codes"
            )
        if role == "error" and template.get("generic") is not True:
            issues.append(
                f"shared error template {template_id!r} must declare generic=true"
            )
        if role == "boundary" and (
            not _is_text(template.get("boundary_condition")) or status not in {"PASS", "FAIL"}
        ):
            issues.append(
                f"boundary template {template_id!r} needs a boundary_condition and disposition"
            )
        if role == "inference-overreach" and (
            mutation.get("operator") != "replace-result-claim-type"
            or status != "FAIL"
            or CAPABILITY_ERROR not in codes
        ):
            issues.append(
                f"inference template {template_id!r} must exercise the capability ceiling and "
                f"expect {CAPABILITY_ERROR}"
            )

    family_cases_raw = manifest.get("family_error_cases")
    if not isinstance(family_cases_raw, list) or not family_cases_raw:
        issues.append("manifest.family_error_cases must be a non-empty array")
        family_cases_raw = []
    family_specific_by_family: dict[str, list[Mapping[str, Any]]] = {}
    family_case_ids: set[str] = set()
    family_specific_case_count = 0
    for index, case in enumerate(family_cases_raw):
        prefix = f"family_error_cases[{index}]"
        if not isinstance(case, Mapping):
            issues.append(f"{prefix} must be an object")
            continue
        case_id = case.get("id")
        family = case.get("family")
        if not _is_text(case_id):
            issues.append(f"{prefix}.id must be non-empty")
            continue
        if case_id in family_case_ids:
            issues.append(f"duplicate family-specific case id: {case_id}")
            continue
        family_case_ids.add(str(case_id))
        if not _is_text(family):
            issues.append(f"family-specific case {case_id!r} lacks a family")
            continue
        family = str(family)
        family_specific_by_family.setdefault(family, []).append(case)
        family_specific_case_count += 1
        if case.get("role") != "error":
            issues.append(f"family-specific case {case_id!r} must declare role error")
        if case.get("generic") is not False:
            issues.append(f"family-specific case {case_id!r} must declare generic=false")
        applicability = case.get("applicability")
        if not isinstance(applicability, Mapping) or applicability.get("families") != [family]:
            issues.append(
                f"family-specific case {case_id!r} applicability must name only {family!r}"
            )
        if not _is_text(case.get("failure_mode")):
            issues.append(f"family-specific case {case_id!r} lacks a failure_mode")
        harness = case.get("harness")
        if harness not in harnesses:
            issues.append(f"family-specific case {case_id!r} references unknown harness")
        if case.get("semantic_validator") != harness:
            issues.append(
                f"family-specific case {case_id!r} must bind its semantic_validator to its harness"
            )
        elif isinstance(harnesses.get(harness), Mapping):
            test_ids = harnesses[harness].get("test_ids")
            if not isinstance(test_ids, list) or not any(
                str(item).endswith(".test_family_specific_error_cases_execute")
                for item in test_ids
            ):
                issues.append(
                    f"family-specific case {case_id!r} harness lacks the executable family-case test"
                )
        source_id = case.get("source_manifest")
        source_variant = case.get("source_variant")
        if source_id not in source_manifests:
            issues.append(
                f"family-specific case {case_id!r} references unknown source manifest"
            )
        elif source_variant not in source_variants.get(source_id, set()):
            issues.append(
                f"family-specific case {case_id!r} source variant {source_variant!r} is not declared"
            )
        mutation = case.get("mutation")
        if not isinstance(mutation, Mapping) or mutation.get("operator") != "replace-method-field":
            issues.append(
                f"family-specific case {case_id!r} needs replace-method-field mutation"
            )
            mutation = {}
        target = mutation.get("target")
        target_prefix = "runs[].method_fields."
        field_name = (
            target.removeprefix(target_prefix)
            if isinstance(target, str) and target.startswith(target_prefix)
            else ""
        )
        if not field_name or not _is_text(mutation.get("value")):
            issues.append(f"family-specific case {case_id!r} has an invalid typed mutation")
        specification = families_value.get(family)
        execution_fields = (
            specification.get("execution_fields")
            if isinstance(specification, Mapping)
            else []
        )
        if field_name and field_name not in (execution_fields or []):
            issues.append(
                f"family-specific case {case_id!r} mutates a field not owned by {family!r}"
            )
        expected = case.get("expected")
        codes = expected.get("codes") if isinstance(expected, Mapping) else None
        if (
            not isinstance(expected, Mapping)
            or expected.get("status") != "FAIL"
            or not isinstance(codes, list)
            or not codes
            or not all(_is_text(code) for code in codes)
        ):
            issues.append(
                f"family-specific case {case_id!r} must expect FAIL with validator codes"
            )
            codes = []
        registered_rules = family_semantic_rules.get(family, {})
        for code in codes:
            rule = registered_rules.get(code)
            if rule is None:
                issues.append(
                    f"family-specific case {case_id!r} expects code outside {family!r}'s semantic validator: {code}"
                )
            elif rule.get("field") != field_name:
                issues.append(
                    f"family-specific case {case_id!r} mutation field does not match validator code {code}"
                )

    family_rows = manifest.get("families")
    if not isinstance(family_rows, list):
        issues.append("manifest.families must be an array")
        family_rows = []
    rows: dict[str, Mapping[str, Any]] = {}
    instantiated_case_count = family_specific_case_count
    used_templates: set[str] = set()
    for index, row in enumerate(family_rows):
        prefix = f"families[{index}]"
        if not isinstance(row, Mapping):
            issues.append(f"{prefix} must be an object")
            continue
        family = row.get("family")
        if not _is_text(family):
            issues.append(f"{prefix}.family must be non-empty")
            continue
        if family in rows:
            issues.append(f"duplicate family coverage row: {family}")
            continue
        rows[family] = row
        template_ids = row.get("case_templates")
        if not isinstance(template_ids, list) or not all(_is_text(item) for item in template_ids):
            issues.append(f"family {family!r}.case_templates must be a string array")
            continue
        if len(template_ids) != len(set(template_ids)):
            issues.append(f"family {family!r} repeats a case template")
        instantiated_case_count += len(template_ids)
        selected: list[Mapping[str, Any]] = []
        for template_id in template_ids:
            template = templates.get(template_id)
            if template is None:
                issues.append(f"family {family!r} references unknown template {template_id!r}")
                continue
            selected.append(template)
            used_templates.add(template_id)
        roles = {template.get("role") for template in selected}
        missing_roles = sorted(REQUIRED_ROLES - roles)
        if missing_roles:
            issues.append(
                f"family {family!r} lacks required semantic roles: {', '.join(missing_roles)}"
            )
        errors = [template for template in selected if template.get("role") == "error"]
        if len(errors) >= 2:
            identities = {
                "failure_mode": {template.get("failure_mode") for template in errors},
                "mutation": {_canonical(template.get("mutation")) for template in errors},
                "expected_codes": {
                    tuple(sorted(template.get("expected", {}).get("codes", [])))
                    for template in errors
                },
            }
            for identity, values in identities.items():
                if len(values) != len(errors):
                    issues.append(
                        f"family {family!r} generic error templates are not distinct by {identity}"
                    )
        family_errors = family_specific_by_family.get(family, [])
        if len(family_errors) < minimum_family_errors:
            issues.append(
                f"family {family!r} has {len(family_errors)} non-generic family-specific error cases; "
                f"requires {minimum_family_errors}"
            )
        else:
            identities = {
                "failure_mode": {case.get("failure_mode") for case in family_errors},
                "mutation": {_canonical(case.get("mutation")) for case in family_errors},
                "expected_codes": {
                    tuple(sorted(case.get("expected", {}).get("codes", [])))
                    for case in family_errors
                },
            }
            for identity, values in identities.items():
                if len(values) < minimum_family_errors:
                    issues.append(
                        f"family {family!r} family-specific error cases are not distinct by {identity}"
                    )
        inference = row.get("inference_overreach")
        if not isinstance(inference, Mapping):
            issues.append(f"family {family!r}.inference_overreach must be an object")
            continue
        inference_template_id = inference.get("template_id")
        inference_template = templates.get(inference_template_id)
        if inference_template_id not in template_ids or (
            inference_template is not None
            and inference_template.get("role") != "inference-overreach"
        ):
            issues.append(
                f"family {family!r} inference_overreach.template_id must select an inference case"
            )
        attempted = inference.get("attempted_claim_type")
        if attempted not in known_claim_types:
            issues.append(
                f"family {family!r} inference overreach uses unknown claim type {attempted!r}"
            )
        allowed = set(capabilities.get(family) or [])
        if attempted in allowed:
            issues.append(
                f"family {family!r} inference case is not an overreach; {attempted!r} is allowed"
            )

    row_families = set(rows)
    executable_set = set(executable)
    for family in sorted(executable_set - row_families):
        issues.append(f"executable registry family lacks coverage: {family}")
    for family in sorted(row_families - executable_set):
        issues.append(f"coverage row does not identify an executable registry family: {family}")
    for family in sorted(set(family_specific_by_family) - executable_set):
        issues.append(
            f"family-specific error case names a non-executable registry family: {family}"
        )
    for family in sorted(executable_set - set(family_semantic_rules)):
        issues.append(f"executable family lacks runtime semantic rules: {family}")
    for family in sorted(set(family_semantic_rules) - executable_set):
        issues.append(f"runtime semantic rules name a non-executable family: {family}")
    for family in sorted(executable_set & set(family_semantic_rules)):
        declared_codes = set(family_semantic_rules[family])
        covered_codes = {
            code
            for case in family_specific_by_family.get(family, [])
            for code in case.get("expected", {}).get("codes", [])
            if isinstance(code, str)
        }
        for code in sorted(declared_codes - covered_codes):
            issues.append(
                f"runtime semantic validator code lacks an executable case for {family!r}: {code}"
            )
    for template_id in sorted(set(templates) - used_templates):
        issues.append(f"case template is never instantiated by a family: {template_id}")

    return CoverageReport(
        issues=tuple(issues),
        executable_families=executable,
        instantiated_case_count=instantiated_case_count,
    )


def check(
    root: Path = ROOT,
    registry_path: Path = DEFAULT_REGISTRY,
    cases_path: Path = DEFAULT_CASES,
) -> CoverageReport:
    root = root.resolve()
    resolved_registry = registry_path if registry_path.is_absolute() else root / registry_path
    resolved_cases = cases_path if cases_path.is_absolute() else root / cases_path
    issues: list[str] = []
    try:
        registry = _load_json(resolved_registry)
    except (OSError, json.JSONDecodeError) as exc:
        return CoverageReport((f"cannot read registry: {exc}",), (), 0)
    try:
        manifest = _load_json(resolved_cases)
    except (OSError, json.JSONDecodeError) as exc:
        return CoverageReport((f"cannot read methodology cases: {exc}",), (), 0)
    if not isinstance(registry, Mapping):
        issues.append("method registry root must be an object")
    if not isinstance(manifest, Mapping):
        issues.append("methodology case manifest root must be an object")
    if issues:
        return CoverageReport(tuple(issues), (), 0)
    try:
        registry_relative = resolved_registry.resolve().relative_to(root).as_posix()
    except ValueError:
        return CoverageReport(("checked registry must be inside the repository",), (), 0)
    return validate_coverage(
        root,
        registry,
        manifest,
        registry_relative_path=Path(registry_relative),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", required=True)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    args = parser.parse_args()
    report = check(args.root, args.registry, args.cases)
    if report.issues:
        print("Methodology coverage check: FAIL")
        for issue in report.issues:
            print(f"- {issue}")
        return 1
    print(
        "Methodology coverage check: PASS "
        f"({len(report.executable_families)} families, "
        f"{report.instantiated_case_count} semantic cases)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
