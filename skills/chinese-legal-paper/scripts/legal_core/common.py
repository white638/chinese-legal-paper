"""Portable file bindings and conservative JSON Schema validation."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import uuid
from datetime import date, datetime


SKILL = Path(__file__).resolve().parents[2]
PROFILE = "chinese-law-v1"
FILES = {
    "sources": "reference_materials/legal_sources.json",
    "analysis": "legal_analysis.json",
    "citations": "legal_citations.json",
    "review": "legal_review.json",
}


def controller():
    scripts = SKILL.parent / "cnki-paper" / "scripts"
    if not (scripts / "avereth.py").is_file():
        raise LegalError("CONTROLLER.MISSING", "Install the matching cnki-paper runtime beside this skill")
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    from avereth_core import config, workflow_registry
    return config, workflow_registry


class LegalError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def scoped(root, relative):
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise LegalError("PATH.INVALID", "Use a nonempty workspace-relative POSIX path")
    root = Path(root).resolve()
    candidate = Path(relative)
    if candidate.is_absolute() or re.match(r"^[A-Za-z]:", relative) or ".." in candidate.parts:
        raise LegalError("PATH.ESCAPE", "Path must stay inside the workspace")
    resolved = (root / candidate).resolve()
    if not resolved.is_relative_to(root) or resolved == root:
        raise LegalError("PATH.ESCAPE", "Resolved path escapes the workspace")
    return resolved


def read_json(path):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON member")
            result[key] = value
        return result
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"),
                          object_pairs_hook=unique_object,
                          parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
    except (OSError, ValueError) as exc:
        raise LegalError("JSON.INVALID", f"Cannot read valid JSON: {Path(path).name}") from exc


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    # Windows tempfile can retry PermissionError indefinitely on a readable but
    # unwritable directory. A UUID/O_EXCL write preserves the actual error.
    temp = path.parent / (".legal-" + uuid.uuid4().hex + ".tmp")
    fd = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def iso_date(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise LegalError("DATE.INVALID", "Expected an ISO YYYY-MM-DD calendar date") from exc


def binding(root, item, *, text=False):
    path = scoped(root, item.get("path"))
    if not path.is_file():
        raise LegalError("BINDING.MISSING", f"Missing bound file: {item.get('path')}")
    if item.get("sha256") != file_hash(path):
        raise LegalError("BINDING.STALE", f"File changed: {item.get('path')}")
    if path.stat().st_size == 0:
        raise LegalError("BINDING.EMPTY", "A bound evidence or review file cannot be empty")
    if text:
        try:
            return path.read_text(encoding="utf-8-sig")
        except UnicodeError as exc:
            raise LegalError("TEXT.REQUIRED", "Text anchors require UTF-8 extracted text") from exc
    return path


def excerpt(root, anchor):
    content = binding(root, anchor, text=True)
    start, end = anchor.get("start"), anchor.get("end")
    if (type(start) is not int or type(end) is not int or not 0 <= start < end <= len(content)):
        raise LegalError("ANCHOR.RANGE", "Invalid zero-based Unicode character offsets")
    actual = content[start:end]
    if actual != anchor.get("quote"):
        raise LegalError("ANCHOR.MISMATCH", "Quoted text does not match the bound character range")
    return actual


def schema_errors(value, schema, path="$", *, root_schema=None):
    """Validate the documented subset; reject unsupported assertions, never skip them.

    The same conservative validator handles bundled contracts and MCP arguments.
    This is not advertised as a complete JSON Schema implementation.
    """
    initial = root_schema is None
    root_schema = schema if initial else root_schema
    if isinstance(schema, bool):
        return [] if schema else [f"{path}: schema rejects value"]
    if not isinstance(schema, dict):
        return [f"{path}: malformed schema"]
    annotations = {"$schema", "$id", "$comment", "title", "description", "default", "examples",
                   "deprecated", "readOnly", "writeOnly", "$defs", "definitions"}
    supported = {"$ref", "type", "enum", "const", "properties", "required", "additionalProperties",
                 "items", "minItems", "maxItems", "uniqueItems", "minLength", "maxLength", "pattern",
                 "format", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
                 "minProperties", "maxProperties", "anyOf", "oneOf", "allOf", "not"}
    unknown = set(schema) - annotations - supported
    if unknown:
        return [f"{path}: unsupported schema keywords: {', '.join(sorted(unknown))}"]
    if initial:
        def preflight(node):
            if isinstance(node, bool):
                return []
            if not isinstance(node, dict):
                return [f"{path}: malformed nested schema"]
            unknown_nested = set(node) - annotations - supported
            found = [f"{path}: unsupported nested schema keywords: {', '.join(sorted(unknown_nested))}"] if unknown_nested else []
            for key in ("properties", "$defs", "definitions"):
                for child in node.get(key, {}).values():
                    found += preflight(child)
            for key in ("items", "additionalProperties", "not"):
                if key in node:
                    found += preflight(node[key])
            for key in ("allOf", "anyOf", "oneOf"):
                for child in node.get(key, []):
                    found += preflight(child)
            return found
        preflight_errors = preflight(schema)
        if preflight_errors:
            return preflight_errors
    errors = []
    if "$ref" in schema:
        ref = schema["$ref"]
        if not isinstance(ref, str) or not ref.startswith("#/"):
            return [f"{path}: only local nonrecursive schema references are supported"]
        target = root_schema
        try:
            for part in ref[2:].split("/"):
                target = target[part.replace("~1", "/").replace("~0", "~")]
            if target is schema:
                return [f"{path}: recursive schema reference is unsupported"]
            errors += schema_errors(value, target, path, root_schema=root_schema)
        except (KeyError, TypeError, RecursionError):
            return [f"{path}: unresolved or recursive schema reference"]
    checks = {
        "object": lambda x: isinstance(x, dict), "array": lambda x: isinstance(x, list),
        "string": lambda x: isinstance(x, str), "integer": lambda x: type(x) is int,
        "number": lambda x: type(x) in {int, float} and math.isfinite(x),
        "boolean": lambda x: type(x) is bool, "null": lambda x: x is None,
    }
    types = schema.get("type", [])
    types = [types] if isinstance(types, str) else types
    if types and not any(checks.get(t, lambda x: False)(value) for t in types):
        return errors + [f"{path}: expected {types}"]
    if "enum" in schema and not any(type(value) is type(v) and value == v for v in schema["enum"]):
        errors.append(f"{path}: value is outside enum")
    if "const" in schema and (type(value) is not type(schema["const"]) or value != schema["const"]):
        errors.append(f"{path}: incorrect constant")
    for keyword in ("anyOf", "oneOf", "allOf"):
        if keyword in schema:
            outcomes = [not schema_errors(value, s, path, root_schema=root_schema) for s in schema[keyword]]
            if not {"anyOf": any(outcomes), "oneOf": sum(outcomes) == 1, "allOf": all(outcomes)}[keyword]:
                errors.append(f"{path}: {keyword} does not match")
    if "not" in schema and not schema_errors(value, schema["not"], path, root_schema=root_schema):
        errors.append(f"{path}: forbidden value")
    if isinstance(value, dict):
        for name in schema.get("required", []):
            if name not in value:
                errors.append(f"{path}.{name}: required")
        for name, item in value.items():
            subschema = schema.get("properties", {}).get(name, schema.get("additionalProperties", True))
            errors += schema_errors(item, subschema, f"{path}.{name}", root_schema=root_schema)
        for k, op in (("minProperties", lambda n, m: n < m), ("maxProperties", lambda n, m: n > m)):
            if k in schema and op(len(value), schema[k]):
                errors.append(f"{path}: {k} failed")
    elif isinstance(value, list):
        for i, item in enumerate(value):
            errors += schema_errors(item, schema.get("items", True), f"{path}[{i}]", root_schema=root_schema)
        if schema.get("uniqueItems") and len({digest(x) for x in value}) != len(value):
            errors.append(f"{path}: duplicate items")
        for k, op in (("minItems", lambda n, m: n < m), ("maxItems", lambda n, m: n > m)):
            if k in schema and op(len(value), schema[k]):
                errors.append(f"{path}: {k} failed")
    elif isinstance(value, str):
        for k, op in (("minLength", lambda n, m: n < m), ("maxLength", lambda n, m: n > m)):
            if k in schema and op(len(value), schema[k]):
                errors.append(f"{path}: {k} failed")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{path}: pattern failed")
        if "format" in schema:
            if schema["format"] == "date":
                try:
                    iso_date(value)
                except LegalError:
                    errors.append(f"{path}: invalid date")
            elif schema["format"] == "date-time":
                try:
                    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
                    if stamp.tzinfo is None:
                        raise ValueError("missing timezone")
                except ValueError:
                    errors.append(f"{path}: invalid timezone-aware date-time")
            elif schema["format"] not in {"uri", "uri-reference"}:
                errors.append(f"{path}: unsupported format")
            elif schema["format"] == "uri" and not re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", value):
                errors.append(f"{path}: invalid URI")
    elif type(value) in {float, int}:
        for k, op in (("minimum", lambda n, m: n < m), ("maximum", lambda n, m: n > m),
                      ("exclusiveMinimum", lambda n, m: n <= m), ("exclusiveMaximum", lambda n, m: n >= m)):
            if k in schema and op(value, schema[k]):
                errors.append(f"{path}: {k} failed")
    return errors
