#!/usr/bin/env python3
"""Run the optional R renderer and report a hash-bound output inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping

from .contract import (
    ID_PATTERN,
    RENDER_ENV_SCHEMA_VERSION,
    RENDER_LOG_SCHEMA_VERSION,
    RENDERER_PACKAGES,
    SPEC_SCHEMA_VERSION,
    _asset_path,
    _valid_file_format,
    canonical_digest,
    validate_spec,
    validate_spec_assets,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_spec(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, Mapping) or payload.get("schema_version") != SPEC_SCHEMA_VERSION:
        raise ValueError(f"spec must use {SPEC_SCHEMA_VERSION}")
    issues = [*validate_spec(payload), *validate_spec_assets(payload)]
    if any(item.severity == "ERROR" for item in issues):
        detail = "; ".join(f"{item.code}@{item.path}" for item in issues)
        raise ValueError(detail)
    return payload


def render(
    spec_path: Path,
    data_path: Path,
    outdir: Path,
    environment_id: str,
    rscript: str | None = None,
) -> dict[str, Any]:
    spec = _load_spec(spec_path)
    environment_id = environment_id.strip()
    if not ID_PATTERN.fullmatch(environment_id):
        raise ValueError("EXHIBIT.RENDERER.ENVIRONMENT_INVALID: environment_id must be a stable uppercase ID")
    executable = rscript or shutil.which("Rscript")
    if not executable or not Path(executable).is_file():
        raise RuntimeError("EXHIBIT.RENDERER.R_UNAVAILABLE: Rscript is not available")
    backend = Path(__file__).resolve().parent / "backends" / "r" / "render_exhibit.R"
    style = Path(__file__).resolve().parents[2] / "references" / "exhibits" / "style-profiles" / f"{spec['style_profile']}.json"
    recipe = _asset_path("recipe", str(spec["kind"]))
    if not data_path.is_file() or not style.is_file() or not recipe.is_file() or not backend.is_file():
        raise RuntimeError("EXHIBIT.RENDERER.INPUT_MISSING: data, style, or backend file is missing")
    outdir.parent.mkdir(parents=True, exist_ok=True)
    if outdir.exists():
        raise RuntimeError(
            "EXHIBIT.RENDERER.OUTPUT_EXISTS: use a new output directory so the bundle can commit atomically"
        )
    staging = Path(
        tempfile.mkdtemp(prefix=f".{outdir.name}.avereth-exhibit-", dir=outdir.parent)
    )
    committed = False
    try:
        completed = subprocess.run(
            [executable, str(backend), str(spec_path), str(data_path), str(style), str(staging)],
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completed.returncode:
            raise RuntimeError(
                "EXHIBIT.RENDERER.R_FAILED: "
                + (completed.stderr.strip() or completed.stdout.strip() or f"exit {completed.returncode}")
            )
        expected = [staging / f"exhibit.{extension}" for extension in spec.get("formats") or []]
        expected.append(staging / "render_log.json")
        missing = [path.name for path in expected if not path.is_file()]
        if missing:
            raise RuntimeError("EXHIBIT.RENDERER.OUTPUT_MISSING: " + ", ".join(missing))
        expected_names = {path.name for path in expected}
        observed_names = {path.name for path in staging.iterdir() if path.is_file()}
        if observed_names != expected_names or any(path.is_dir() for path in staging.iterdir()):
            raise RuntimeError(
                "EXHIBIT.RENDERER.OUTPUT_UNDECLARED: renderer outputs must exactly match the declared formats and render_log"
            )
        for output_path in expected[:-1]:
            declared_format = output_path.suffix.lstrip(".").casefold()
            if not _valid_file_format(output_path, declared_format):
                raise RuntimeError(
                    "EXHIBIT.FORMAT.INVALID: "
                    f"{output_path.name} does not match {declared_format}"
                )
        try:
            render_log = json.loads(expected[-1].read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"EXHIBIT.RENDERER.LOG_INVALID: {exc}") from exc
        if (
            not isinstance(render_log, Mapping)
            or render_log.get("schema_version") != RENDER_LOG_SCHEMA_VERSION
            or render_log.get("exhibit_id") != spec.get("exhibit_id")
            or not isinstance(render_log.get("render_checks"), Mapping)
            or not str(render_log.get("R") or "").strip()
            or not isinstance(render_log.get("packages"), Mapping)
            or set(render_log.get("packages") or {}) != RENDERER_PACKAGES
            or not all(str(value).strip() for value in (render_log.get("packages") or {}).values())
            or not isinstance(render_log.get("requested_fonts"), Mapping)
            or set(render_log.get("requested_fonts") or {}) != {"base"}
            or not str((render_log.get("requested_fonts") or {}).get("base") or "").strip()
            or not isinstance(render_log.get("resolved_fonts"), Mapping)
            or set(render_log.get("resolved_fonts") or {}) != {"base"}
            or not str((render_log.get("resolved_fonts") or {}).get("base") or "").strip()
            or not isinstance((render_log.get("render_checks") or {}).get("font_fallback_used"), bool)
        ):
            raise RuntimeError(
                "EXHIBIT.RENDERER.LOG_INVALID: render log identity or checks are missing"
            )
        environment_snapshot = {
            "schema_version": RENDER_ENV_SCHEMA_VERSION,
            "renderer": str(render_log.get("renderer") or ""),
            "R": str(render_log.get("R") or ""),
            "packages": render_log.get("packages") or {},
            "requested_fonts": render_log.get("requested_fonts") or {},
            "resolved_fonts": render_log.get("resolved_fonts") or {},
            "backend_sha256": _sha256(backend),
            "style_profile_sha256": _sha256(style),
            "recipe_sha256": _sha256(recipe),
        }
        input_hashes = {
            "spec_sha256": canonical_digest(spec),
            "data_sha256": _sha256(data_path),
            "style_sha256": _sha256(style),
            "recipe_sha256": _sha256(recipe),
            "backend_sha256": _sha256(backend),
        }
        output_hashes = [
            {
                "format": source.suffix.lstrip(".").casefold(),
                "sha256": _sha256(source),
            }
            for source in expected[:-1]
        ]
        render_log = dict(render_log)
        render_log["software_environment_id"] = environment_id
        render_log["software_environment"] = environment_snapshot
        render_log["software_environment_sha256"] = canonical_digest(environment_snapshot)
        render_log["inputs"] = input_hashes
        render_log["outputs"] = output_hashes
        expected[-1].write_text(
            json.dumps(render_log, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        records: list[dict[str, str]] = []
        for source in expected:
            records.append({"path": source.name, "sha256": _sha256(source)})
        staging.replace(outdir)
        committed = True
        return {
            "schema_version": "avereth-exhibit-render-report/v1",
            "exhibit_id": spec["exhibit_id"],
            "spec_sha256": canonical_digest(spec),
            "renderer": render_log["renderer"],
            "render_checks": render_log["render_checks"],
            "software_environment_id": environment_id,
            "software_environment": environment_snapshot,
            "software_environment_sha256": render_log["software_environment_sha256"],
            "inputs": input_hashes,
            "files": records,
        }
    finally:
        if not committed and staging.exists():
            shutil.rmtree(staging)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--environment-id", required=True)
    parser.add_argument("--rscript")
    args = parser.parse_args(argv)
    try:
        manifest = render(
            args.spec,
            args.data,
            args.out,
            args.environment_id,
            args.rscript,
        )
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 3
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
