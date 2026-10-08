"""Single format route table for output rendering and guards."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def enabled(value: object, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"", "0", "false", "no", "none", "off"}


def word_requested(config: dict[str, Any]) -> bool:
    return enabled(config.get("word_output", "docx"), default=True)


def pdf_requested(config: dict[str, Any], canonical: Path) -> bool:
    value = str(config.get("pdf_output") or "").strip().lower()
    if value in {"pdf", "true", "yes", "1", "required"}:
        return True
    if value in {"none", "false", "no", "0", "disabled"}:
        return False
    # Stable ``auto`` means source-format policy, never machine capability.
    return canonical.suffix.lower() == ".tex"


def word_relative(config: dict[str, Any]) -> str:
    language = str(config.get("output_language") or "en").strip().lower()
    return "final_paper/paper.zh.docx" if language == "zh" else "final_paper/paper.docx"


def primary_delivery_relatives(config: dict[str, Any], canonical: Path) -> tuple[str, ...]:
    relatives: list[str] = []
    if word_requested(config):
        relatives.append(word_relative(config))
    if pdf_requested(config, canonical):
        relatives.append("final_paper/paper.pdf")
    return tuple(relatives)


def package_enabled(config: dict[str, Any], key: str) -> bool:
    return str(config.get(key) or "none").strip().lower() not in {
        "", "none", "false", "0", "off"
    }


def _safe_names(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    names: list[str] = []
    for item in value:
        token = str(item or "").strip().replace("\\", "/")
        path = Path(token)
        if token and not path.is_absolute() and ".." not in path.parts:
            names.append(path.as_posix())
    return tuple(sorted(set(names)))


def translation_delivery_relatives(config: dict[str, Any]) -> tuple[str, ...]:
    if not package_enabled(config, "translation_package"):
        return ()
    return (
        "translation_zh/paper.zh.docx",
        "translation_zh/translation_coverage.md",
        "translation_zh/translation_manifest.json",
    )


def submission_delivery_relatives(
    config: dict[str, Any],
    primary: tuple[str, ...],
) -> tuple[str, ...]:
    if not package_enabled(config, "submission_package"):
        return ()
    files = [f"submission_package/{Path(relative).name}" for relative in primary]
    files.extend(f"submission_package/{name}" for name in _safe_names(config.get("submission_required_files")))
    files.append("submission_package/submission_manifest.json")
    return tuple(sorted(set(files)))


def response_delivery_relatives(
    config: dict[str, Any],
    primary: tuple[str, ...],
) -> tuple[str, ...]:
    mode = str(config.get("response_package") or "none").strip().lower()
    if mode not in {"review_response", "rebuttal"}:
        return ()
    files = [f"{mode}/{Path(relative).name}" for relative in primary]
    files.extend(f"{mode}/{name}" for name in _safe_names(config.get("response_required_files")))
    files.append(f"{mode}/response_manifest.json")
    return tuple(sorted(set(files)))


def submission_preview_relative(name: str) -> str:
    return f"render_qa/submission_package/{Path(name).as_posix()}.pdf"


def preview_relatives(config: dict[str, Any]) -> tuple[str, ...]:
    previews: list[str] = []
    if word_requested(config):
        previews.append("render_qa/word_preview.pdf")
    if package_enabled(config, "translation_package"):
        previews.append("render_qa/translation_preview.pdf")
    if package_enabled(config, "submission_package"):
        previews.extend(
            submission_preview_relative(name)
            for name in _safe_names(config.get("submission_required_files"))
            if name.lower().endswith(".docx")
        )
    return tuple(sorted(previews))


def delivery_relatives(config: dict[str, Any], canonical: Path) -> tuple[str, ...]:
    primary = primary_delivery_relatives(config, canonical)
    return tuple(sorted({
        *primary,
        *translation_delivery_relatives(config),
        *submission_delivery_relatives(config, primary),
        *response_delivery_relatives(config, primary),
    }))
