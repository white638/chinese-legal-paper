#!/usr/bin/env python3
"""Contract and adversarial-fixture checks for the public-text-politics pack."""

from __future__ import annotations

import copy
import json
import re
import unittest
from collections import Counter
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PACK = ROOT / "skills" / "empirical-research" / "packs" / "public-text-politics"
REGISTRY = ROOT / "skills" / "empirical-research" / "references" / "method-adapter-registry.json"
FIXTURE_KINDS = {"positive": 1, "typical-error": 2, "boundary": 1, "inference-overreach": 1}
PROFILE_IDS = {
    "claim_measurement",
    "semantic_alignment_and_reuse",
    "legislative_process",
    "institutional_grammar",
    "public_source_process_tracing",
    "discourse_network",
    "text_in_causal_design",
}
def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _pointer(document: Any, pointer: str) -> Any:
    current = document
    if pointer in {"", "/"}:
        return current
    for raw in pointer.lstrip("/").split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        current = current[int(token)] if isinstance(current, list) else current[token]
    return current


def _pointer_parent(document: Any, pointer: str) -> tuple[Any, str | int]:
    parts = pointer.lstrip("/").split("/")
    if not pointer.startswith("/") or not parts or parts == [""]:
        raise AssertionError(f"operation requires non-root JSON Pointer: {pointer!r}")
    parent_pointer = "/" + "/".join(parts[:-1]) if len(parts) > 1 else ""
    parent = _pointer(document, parent_pointer)
    token = parts[-1].replace("~1", "/").replace("~0", "~")
    return parent, int(token) if isinstance(parent, list) else token


def _apply_operations(document: dict[str, Any], operations: list[dict[str, Any]]) -> None:
    for operation in operations:
        if operation.get("op") != "replace":
            raise AssertionError(f"only deterministic replace operations are allowed: {operation!r}")
        parent, key = _pointer_parent(document, operation["path"])
        actual = parent[key]
        if actual != operation["from"]:
            raise AssertionError(
                f"fixture drift at {operation['path']}: expected {operation['from']!r}, got {actual!r}"
            )
        parent[key] = copy.deepcopy(operation["value"])


def _expand_artifacts(value: Any, prefix: str) -> Any:
    if isinstance(value, str) and value.startswith(prefix):
        logical_name = re.sub(r"[^A-Z0-9]+", "-", value[len(prefix) :].upper()).strip("-")
        return f"ART-{logical_name}"
    if isinstance(value, list):
        return [_expand_artifacts(item, prefix) for item in value]
    if isinstance(value, dict):
        return {key: _expand_artifacts(item, prefix) for key, item in value.items()}
    return value


def _type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    raise AssertionError(f"unsupported schema type in fixture evaluator: {expected}")


def _schema_errors(
    value: Any,
    schema: dict[str, Any],
    root: dict[str, Any],
    path: str = "",
    inherited_code: str | None = None,
) -> list[str]:
    """Evaluate the deliberately small JSON-Schema subset used by this pack.

    This is an executable fixture harness, not a replacement for the runtime method
    validator. It keeps the checked-in contracts dependency-free and catches schema/
    fixture drift in CI.
    """

    code = inherited_code or schema.get("x-error-code")
    if "$ref" in schema:
        ref = schema["$ref"]
        if not ref.startswith("#/"):
            raise AssertionError(f"only local schema refs are allowed: {ref}")
        target = _pointer(root, ref[1:])
        return _schema_errors(value, target, root, path, code)

    errors: list[str] = []

    def fail(label: str) -> None:
        errors.append(code or f"SCHEMA.{label}:{path or '/'}")

    if "const" in schema and value != schema["const"]:
        fail("CONST")
        return errors
    if "enum" in schema and value not in schema["enum"]:
        fail("ENUM")
        return errors
    if "type" in schema and not _type_matches(value, schema["type"]):
        fail("TYPE")
        return errors

    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            fail("MIN_LENGTH")
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            fail("PATTERN")
    elif isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            fail("MIN_ITEMS")
        if schema.get("uniqueItems"):
            frozen = [json.dumps(item, ensure_ascii=False, sort_keys=True) for item in value]
            if len(set(frozen)) != len(frozen):
                fail("UNIQUE_ITEMS")
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(value):
                errors.extend(_schema_errors(item, item_schema, root, f"{path}/{index}", code))
    elif isinstance(value, dict):
        properties = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                property_code = properties.get(key, {}).get("x-error-code")
                errors.append(property_code or code or f"SCHEMA.REQUIRED:{path}/{key}")
        for key, item in value.items():
            if key in properties:
                errors.extend(_schema_errors(item, properties[key], root, f"{path}/{key}", code))
            elif schema.get("additionalProperties") is False:
                errors.append(code or f"SCHEMA.ADDITIONAL_PROPERTY:{path}/{key}")
    return errors


def _recursive_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        keys.update(value)
        for item in value.values():
            keys.update(_recursive_keys(item))
    elif isinstance(value, list):
        for item in value:
            keys.update(_recursive_keys(item))
    return keys


class PublicTextPoliticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = _load(PACK / "manifest.json")
        cls.profile_schema = _load(PACK / "profile.schema.json")
        cls.registry = _load(REGISTRY)
        cls.entries = {entry["id"]: entry for entry in cls.manifest["profiles"]}
        cls.registry_entries: dict[str, tuple[str, dict[str, Any]]] = {}
        for core_id, core_spec in cls.registry["method_contracts"].items():
            for binding in core_spec.get("supplemental_profiles", []):
                profile_id = binding["id"]
                if profile_id in cls.registry_entries:
                    raise AssertionError(f"duplicate supplemental profile binding: {profile_id}")
                cls.registry_entries[profile_id] = (core_id, binding)

    def test_internal_pack_has_exact_profiles_and_no_control_plane(self) -> None:
        self.assertEqual("internal-method-profile-pack", self.manifest["kind"])
        self.assertEqual("cnki-paper", self.manifest["control_plane"])
        self.assertEqual("method-profile-assets-only", self.manifest["ownership"])
        self.assertEqual(PROFILE_IDS, set(self.entries))
        self.assertEqual(PROFILE_IDS, set(self.registry_entries))
        self.assertEqual(
            "core-method-contract-only",
            self.manifest["runtime_binding"]["validator_dispatch"],
        )
        self.assertFalse((PACK / "SKILL.md").exists())
        self.assertFalse((PACK / "agents").exists())
        self.assertFalse((PACK / "examples").exists())
        self.assertNotIn("stages", _recursive_keys(self.manifest))
        self.assertNotIn("receipts", _recursive_keys(self.manifest))
        forbidden_ownership_keys = {
            "stage",
            "stages",
            "status",
            "receipt",
            "receipts",
            "gate",
            "next_stage",
            "completed_stage",
            "router",
        }
        for path in PACK.rglob("*.json"):
            with self.subTest(asset=path.relative_to(PACK).as_posix()):
                self.assertTrue(forbidden_ownership_keys.isdisjoint(_recursive_keys(_load(path))))
        forbidden_name_parts = {"router", "status", "receipt"}
        for path in PACK.rglob("*"):
            normalized = path.name.lower().replace("-", "_")
            self.assertFalse(any(part in normalized for part in forbidden_name_parts), path)

    def test_profiles_validate_and_only_reference_core_claim_capabilities(self) -> None:
        guide = (PACK / "CONTRACTS.md").read_text(encoding="utf-8")
        for profile_id, entry in self.entries.items():
            with self.subTest(profile=profile_id):
                profile_path = PACK / entry["profile"]
                profile = _load(profile_path)
                core_id, binding = self.registry_entries[profile_id]
                registered_profile_path = REGISTRY.parent.parent / binding["profile_asset"]
                registered_schema_path = REGISTRY.parent.parent / binding["schema_asset"]
                self.assertEqual(profile_path.resolve(), registered_profile_path.resolve())
                self.assertEqual([], _schema_errors(profile, self.profile_schema, self.profile_schema))
                self.assertEqual(profile_id, profile["profile_id"])
                self.assertEqual(
                    registered_schema_path.resolve(),
                    (profile_path.parent / profile["profile_contract_schema"]).resolve(),
                )
                self.assertEqual(core_id, profile["core_method_contract_id"])
                self.assertEqual(core_id, binding["core_method_contract_id"])
                self.assertEqual(
                    self.registry["method_contracts"][core_id]["revision"],
                    binding["core_method_contract_revision"],
                )
                self.assertIn(f"## {profile_id}", guide)
                self.assertEqual(len(profile["machine_checks"]), len({item["id"] for item in profile["machine_checks"]}))
                self.assertNotIn("claim_capabilities", _recursive_keys(profile))
                self.assertNotIn("inference_ceiling", _recursive_keys(profile))
                for family in profile["core_method_families"]:
                    self.assertIn(family, self.registry["families"])
                    self.assertIn(
                        profile["core_method_contract_id"],
                        self.registry["families"][family]["method_contract_profiles"],
                    )
                for family in profile.get("complementary_method_families", []):
                    self.assertIn(family, self.registry["families"])
                core_spec = self.registry["method_contracts"][core_id]
                self.assertEqual(
                    (PACK / profile["core_method_contract_schema"]).resolve(),
                    (REGISTRY.parent.parent / core_spec["asset"]).resolve(),
                )
                self.assertTrue((PACK / profile["core_method_contract_schema"]).is_file())
                for reference in profile["core_claim_capability_refs"]:
                    relative, fragment = reference.split("#", 1)
                    resolved = (PACK / relative).resolve()
                    self.assertEqual(REGISTRY.resolve(), resolved)
                    capability = _pointer(self.registry, fragment)
                    self.assertIsInstance(capability, list)
                    self.assertTrue(capability)

    def test_contract_schemas_are_closed_and_bound_to_profiles(self) -> None:
        for profile_id in self.entries:
            with self.subTest(profile=profile_id):
                core_id, binding = self.registry_entries[profile_id]
                contract = _load(REGISTRY.parent.parent / binding["schema_asset"])
                self.assertEqual("object", contract["type"])
                self.assertFalse(contract["additionalProperties"])
                self.assertEqual("supplement-over-core-method-contract", contract["x-profile-contract-role"])
                self.assertEqual(core_id, contract["x-core-method-contract-id"])
                self.assertEqual(profile_id, contract["properties"]["profile_id"]["const"])
                self.assertIn("schema_version", contract["required"])
                self.assertIn("interpretation", contract["required"])
                artifact = contract["$defs"]["artifact"]
                self.assertEqual("string", artifact["type"])
                self.assertEqual("^ART-[A-Z0-9][A-Z0-9_-]*$", artifact["pattern"])
                self.assertNotIn("path", artifact)
                self.assertNotIn("sha256", artifact)

    def test_every_profile_has_executable_adversarial_coverage(self) -> None:
        for profile_id, entry in self.entries.items():
            with self.subTest(profile=profile_id):
                fixture = _load(PACK / entry["adversarial_fixture"])
                _, binding = self.registry_entries[profile_id]
                schema = _load(REGISTRY.parent.parent / binding["schema_asset"])
                self.assertEqual("avereth-public-text-politics-executable-fixtures/v1", fixture["schema_version"])
                self.assertEqual(profile_id, fixture["profile_id"])
                self.assertEqual(FIXTURE_KINDS, Counter(case["kind"] for case in fixture["cases"]))
                base = _expand_artifacts(fixture["base_contract"], fixture["artifact_token_prefix"])
                self.assertEqual([], _schema_errors(base, schema, schema))
                for case in fixture["cases"]:
                    payload = copy.deepcopy(base)
                    _apply_operations(payload, case["operations"])
                    codes = set(_schema_errors(payload, schema, schema))
                    if case["expected_status"] == "PASS":
                        self.assertEqual(set(), codes, case["id"])
                    else:
                        self.assertTrue(codes, case["id"])
                        self.assertLessEqual(set(case["expected_codes"]), codes, case["id"])

    def test_supplemental_profiles_cannot_become_core_method_contracts(self) -> None:
        forbidden_authority = {
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
        for profile_id, (core_id, binding) in self.registry_entries.items():
            with self.subTest(profile=profile_id):
                self.assertEqual(
                    {
                        "id",
                        "profile_asset",
                        "schema_asset",
                        "core_method_contract_id",
                        "core_method_contract_revision",
                    },
                    set(binding),
                )
                self.assertTrue(forbidden_authority.isdisjoint(binding))
                schema = _load(REGISTRY.parent.parent / binding["schema_asset"])
                profile = _load(REGISTRY.parent.parent / binding["profile_asset"])
                self.assertTrue(
                    forbidden_authority.isdisjoint(_recursive_keys(schema))
                )
                self.assertTrue(
                    forbidden_authority.isdisjoint(_recursive_keys(profile))
                )
                supplemental_schema_id = schema["properties"]["schema_version"]["const"]
                self.assertNotIn(supplemental_schema_id, self.registry["method_contracts"])
                self.assertEqual(core_id, binding["core_method_contract_id"])

    def test_eval_manifest_matches_pack(self) -> None:
        eval_manifest = _load(HERE / "manifest.json")
        self.assertEqual(sorted(PROFILE_IDS), sorted(eval_manifest["required_profiles"]))
        self.assertEqual(FIXTURE_KINDS, eval_manifest["required_fixture_kinds_per_profile"])
        for golden_project in (
            "white-paper-traceability",
            "trump-congress-agenda",
            "hainan-rcep-compatibility",
        ):
            self.assertFalse(
                (ROOT / "examples" / golden_project).exists(),
                "PR6 golden projects are explicitly out of scope",
            )


if __name__ == "__main__":
    unittest.main()
