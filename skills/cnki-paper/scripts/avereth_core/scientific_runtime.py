"""Content-address the scientific contracts that make an audit reproducible."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable

from .workflow_registry import runtime_files_for


SCIENTIFIC_RUNTIME_GROUPS = frozenset({"research", "methods", "venue"})
METHOD_REGISTRY_REL = "empirical-research/references/method-adapter-registry.json"
VENUE_REGISTRY_REL = "journal-fit/references/venue-overlay-registry.json"
CONTROL_PATHS = (
    "cnki-paper/scripts/avereth_core/workflow_registry.py",
    "cnki-paper/scripts/avereth_core/scientific_runtime.py",
)


def _runtime_asset(root: Path, relative: str) -> Path:
    """Resolve a generated runtime path or its canonical source template."""

    path = root / relative
    if path.is_file() or relative != "cnki-paper/SKILL.md":
        return path
    source_template = root / "cnki-paper/SKILL.source.md"
    return source_template if source_template.is_file() else path


def _controller_runtime_paths(root: Path) -> set[str]:
    """Bind the controller module closure used to sign and verify receipts.

    The controller has package-local and lazy imports that are easy to omit
    from a hand-maintained list.  Hash every non-test runtime source in the
    controller package so a changed gate, receipt reader, lock, or stage
    projection cannot leave an old scientific receipt valid.
    """

    paths: set[str] = set()
    controller_root = root / "cnki-paper/scripts/avereth_core"
    if not controller_root.is_dir():
        return paths
    for path in controller_root.rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        if path.suffix not in {".py", ".ps1"} or path.name.startswith("test_"):
            continue
        paths.add(path.relative_to(root).as_posix())
    return paths


def _registered_method_paths(root: Path) -> set[str]:
    paths = {METHOD_REGISTRY_REL}
    registry = root / METHOD_REGISTRY_REL
    try:
        payload = json.loads(registry.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return paths
    contracts = payload.get("method_contracts")
    if not isinstance(contracts, dict):
        return paths
    for specification in contracts.values():
        if not isinstance(specification, dict):
            continue
        asset = specification.get("asset")
        if isinstance(asset, str) and asset:
            paths.add(f"empirical-research/{asset}")
        validator = specification.get("validator")
        if isinstance(validator, str) and validator:
            paths.add(f"empirical-research/scripts/validators/{validator}.py")
        for profile in specification.get("supplemental_profiles") or []:
            if not isinstance(profile, dict):
                continue
            for field in ("profile_asset", "schema_asset"):
                relative = profile.get(field)
                if isinstance(relative, str) and relative:
                    paths.add(f"empirical-research/{relative}")
    return paths


def _registered_venue_paths(root: Path) -> set[str]:
    paths = {VENUE_REGISTRY_REL}
    venue_root = root / "journal-fit"
    if venue_root.is_dir():
        # The current workflow config has no canonical venue ID, so narrowing
        # this binding to one pack would be guesswork.  Bind the complete
        # overlay tree until an explicit venue fact can select a smaller
        # registered subgraph.
        for path in venue_root.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                paths.add(path.relative_to(root).as_posix())
    registry = root / VENUE_REGISTRY_REL
    try:
        payload = json.loads(registry.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return paths
    for raw in payload.get("workflow_overlays") or []:
        if not isinstance(raw, str) or not raw:
            continue
        normalized = raw.replace("\\", "/")
        if normalized.startswith("skills/"):
            normalized = normalized[len("skills/") :]
        paths.add(normalized)
    return paths


def _default_runtime_paths(root: Path, groups: Iterable[str]) -> tuple[str, ...]:
    selected = frozenset(groups)
    paths = {
        *runtime_files_for(selected | {"core"}),
        *CONTROL_PATHS,
        *_controller_runtime_paths(root),
    }
    if "methods" in selected:
        paths.update(_registered_method_paths(root))
    if "venue" in selected:
        paths.update(_registered_venue_paths(root))
    return tuple(sorted(paths))


def scientific_runtime_manifest(
    skills_dir: Path | None = None,
    *,
    groups: Iterable[str] | None = None,
    relative_paths: Iterable[str] | None = None,
) -> dict[str, str]:
    """Return relative path -> SHA-256 without executing any runtime component."""

    root = (skills_dir or Path(__file__).resolve().parents[3]).resolve()
    selected_groups = tuple(groups) if groups is not None else tuple(SCIENTIFIC_RUNTIME_GROUPS)
    paths = (
        tuple(relative_paths)
        if relative_paths is not None
        else _default_runtime_paths(root, selected_groups)
    )
    manifest: dict[str, str] = {}
    for relative in sorted(set(paths)):
        path = _runtime_asset(root, relative)
        try:
            manifest[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            # Doctor prevents a PASS receipt when a required runtime asset is
            # missing.  Keeping an explicit marker also makes the digest
            # deterministic and fail-closed if this helper is called directly.
            manifest[relative] = "missing"
    return manifest


def scientific_runtime_digest(
    skills_dir: Path | None = None,
    *,
    groups: Iterable[str] | None = None,
    relative_paths: Iterable[str] | None = None,
) -> str:
    manifest = scientific_runtime_manifest(
        skills_dir,
        groups=groups,
        relative_paths=relative_paths,
    )
    payload = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def scientific_runtime_issues(
    skills_dir: Path | None = None,
    *,
    groups: Iterable[str] | None = None,
) -> list[str]:
    """Return deterministic missing-asset findings for receipt signing."""

    return [
        f"scientific runtime asset is missing: {relative}"
        for relative, digest in scientific_runtime_manifest(skills_dir, groups=groups).items()
        if digest == "missing"
    ]
