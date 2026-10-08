"""Canonical manuscript selection and conservative draft promotion."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..artifacts import sha256_file


SUPPORTED_SUFFIXES = {".tex", ".md", ".docx"}
DEFAULT_CANDIDATES = (
    Path("final_paper/main.tex"),
    Path("final_paper/main.md"),
    Path("final_paper/main.docx"),
    Path("final_paper/paper.md"),
    Path("final_paper/manuscript.md"),
    Path("final_paper/manuscript.docx"),
)


class ManuscriptSelectionError(ValueError):
    """Raised when a workspace has no safe, unique canonical manuscript."""


@dataclass(frozen=True)
class ManuscriptSelection:
    path: Path
    relative_path: str
    sha256: str

    def as_dict(self) -> dict[str, str]:
        return {"path": self.relative_path, "sha256": self.sha256}


@dataclass(frozen=True)
class PreparedManuscript:
    selection: ManuscriptSelection
    promoted_path: Path | None = None


def _inside_workspace(outdir: Path, raw: str | Path) -> Path:
    root = outdir.resolve()
    candidate = Path(raw)
    resolved = (candidate if candidate.is_absolute() else outdir / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ManuscriptSelectionError("canonical manuscript must stay inside the workspace") from exc
    if resolved.suffix.lower() not in SUPPORTED_SUFFIXES:
        allowed = ", ".join(sorted(SUPPORTED_SUFFIXES))
        raise ManuscriptSelectionError(f"canonical manuscript must use one of: {allowed}")
    if not resolved.is_file() or resolved.stat().st_size <= 0:
        raise ManuscriptSelectionError(f"canonical manuscript is missing or empty: {resolved}")
    return resolved


def select_manuscript(outdir: Path, config: dict[str, Any] | None = None) -> ManuscriptSelection:
    """Select exactly one manuscript and bind its workspace-relative SHA256."""

    active = dict(config or {})
    explicit = str(
        active.get("canonical_manuscript")
        or active.get("citation_audit_manuscript")
        or ""
    ).strip()
    if explicit:
        selected = _inside_workspace(outdir, explicit)
    else:
        present: list[Path] = []
        for relative in DEFAULT_CANDIDATES:
            candidate = outdir / relative
            if candidate.is_file() and candidate.stat().st_size > 0:
                present.append(candidate.resolve())
        if not present:
            raise ManuscriptSelectionError(
                "no canonical manuscript found; declare canonical_manuscript or create one supported final_paper source"
            )
        if len(present) != 1:
            rendered = ", ".join(path.relative_to(outdir.resolve()).as_posix() for path in present)
            raise ManuscriptSelectionError(
                f"multiple manuscript sources exist ({rendered}); declare canonical_manuscript explicitly"
            )
        selected = present[0]
    relative = selected.relative_to(outdir.resolve()).as_posix()
    return ManuscriptSelection(selected, relative, sha256_file(selected))


def prepare_manuscript(outdir: Path, config: dict[str, Any] | None = None) -> PreparedManuscript:
    """Promote an explicitly registered draft only when no canonical source exists.

    The source draft is never moved or overwritten.  Promotion is an atomic
    copy into ``final_paper/main.<suffix>`` and is intentionally unavailable
    for ambiguous workspaces.
    """

    active = dict(config or {})
    raw_draft = str(active.get("draft_path") or "").strip()
    explicit = str(active.get("canonical_manuscript") or "").strip()
    try:
        selected = select_manuscript(outdir, active)
        if raw_draft and not explicit:
            draft = _inside_workspace(outdir, raw_draft)
            if sha256_file(draft) != selected.sha256:
                raise ManuscriptSelectionError(
                    "the registered draft changed after promotion; explicitly refresh the final source or set canonical_manuscript"
                )
        return PreparedManuscript(selected)
    except ManuscriptSelectionError as original:
        if explicit or not raw_draft:
            raise original
    draft = _inside_workspace(outdir, raw_draft)
    # Do not silently choose among competing final sources.
    competing = [relative for relative in DEFAULT_CANDIDATES if (outdir / relative).is_file()]
    if competing:
        raise ManuscriptSelectionError(
            "cannot promote draft while another final_paper manuscript source exists"
        )
    destination = outdir / "final_paper" / f"main{draft.suffix.lower()}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    shutil.copy2(draft, temporary)
    temporary.replace(destination)
    selection = select_manuscript(
        outdir,
        {**active, "canonical_manuscript": destination.relative_to(outdir).as_posix()},
    )
    return PreparedManuscript(selection, destination)


def promote_draft(outdir: Path, config: dict[str, Any] | None = None) -> ManuscriptSelection:
    """Compatibility convenience returning only the prepared selection."""

    return prepare_manuscript(outdir, config).selection


def rollback_preparation(prepared: PreparedManuscript) -> None:
    """Remove only the exact file created by this preparation attempt."""

    promoted = prepared.promoted_path
    if promoted is not None and promoted.is_file():
        promoted.unlink()
