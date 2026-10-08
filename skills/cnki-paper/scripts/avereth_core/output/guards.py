"""Run guards against staged deliveries; academic audit is never rerun."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from ..artifacts import report_passed
from ..build.manuscript import ManuscriptSelection
from ..config import read_config
from ..models import Finding, GateResult
from .policy import package_enabled, word_relative, word_requested
from .response import mode as response_mode


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"


def required_tool_scripts(config: dict[str, Any], canonical: Path) -> tuple[str, ...]:
    scripts: list[str] = []
    if canonical.suffix.lower() == ".tex":
        scripts.append("latex_guard.py")
        if config.get("max_sections") is not None:
            scripts.append("section_economy_check.py")
    submission_docx = package_enabled(config, "submission_package") and any(
        str(item or "").strip().lower().endswith(".docx")
        for item in (config.get("submission_required_files") or [])
    )
    if word_requested(config) or package_enabled(config, "translation_package") or submission_docx:
        scripts.append("word_guard.py")
    return tuple(scripts)


def required_report_relatives(config: dict[str, Any], canonical: Path) -> tuple[str, ...]:
    """Return the exact durable guard reports required by an output route."""

    reports: list[str] = []
    if canonical.suffix.lower() == ".tex":
        reports.append("latex_guard.md")
        if config.get("max_sections") is not None:
            reports.append("section_economy_check.md")
    if word_requested(config):
        reports.append(
            "word_report.zh.md"
            if word_relative(config).endswith("zh.docx")
            else "word_report.md"
        )
    if package_enabled(config, "translation_package"):
        reports.append("translation_guard.md")
        reports.append("translation_word_report.md")
    if package_enabled(config, "submission_package"):
        reports.append("submission_check.md")
    if response_mode(config) != "none":
        reports.append("respond_check.md")
    return tuple(reports)


def _run(script: str, arguments: list[str]) -> tuple[int, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        result = subprocess.run(
            [sys.executable, str(TOOLS_DIR / script), *arguments],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            check=False,
            timeout=300,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 2, str(exc)
    return result.returncode, " ".join((result.stdout + "\n" + result.stderr).split())[-1600:]


def _write_report(
    path: Path,
    title: str,
    code: int,
    detail: str,
    *,
    existing_detail: str = "",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = existing_detail.strip() or detail or "No diagnostic output."
    path.write_text(
        "\n".join([
            f"# {title}",
            "",
            f"Status: {'PASS' if code == 0 else 'FAIL'}",
            "",
            "## Guard Detail",
            "",
            body,
            "",
        ]),
        encoding="utf-8",
    )


def run_guards(
    outdir: Path,
    *,
    config: dict[str, Any] | None = None,
    canonical: ManuscriptSelection | None = None,
    delivery_root: Path | None = None,
    report_root: Path | None = None,
) -> GateResult:
    """Validate staged output without overwriting published delivery files."""

    active = dict(config if config is not None else read_config(outdir).payload)
    delivery_root = delivery_root or outdir
    report_root = report_root or outdir
    findings: list[Finding] = []
    generated: list[str] = []
    if canonical is None:
        return GateResult.blocked(
            "output",
            [Finding("OUTPUT.CANONICAL_MISSING", "output guards require the audit-bound canonical manuscript")],
        )
    for script in required_tool_scripts(active, canonical.path):
        if not (TOOLS_DIR / script).is_file():
            findings.append(Finding("OUTPUT.GUARD_MISSING", f"required output guard is missing: {script}"))
    if findings:
        return GateResult.blocked("output", findings)

    for relative in ("translation_guard.md", "submission_check.md", "respond_check.md"):
        if relative not in required_report_relatives(active, canonical.path):
            continue
        report = report_root / relative
        if report_passed(report):
            generated.append(relative)
        else:
            findings.append(Finding(
                "OUTPUT.GUARD_REPORT_INVALID",
                f"staged package guard is missing or not PASS: {relative}",
                relative,
            ))

    if canonical.path.suffix.lower() == ".tex":
        arguments = [
            str(canonical.path), "--markdown", "--citation-mode",
            str(active.get("citation_mode") or "numeric"),
        ]
        bib = canonical.path.parent / "references.bib"
        if bib.is_file():
            arguments.extend(["--bib", str(bib)])
        code, detail = _run("latex_guard.py", arguments)
        report = report_root / "latex_guard.md"
        _write_report(report, "LaTeX Guard", code, detail)
        generated.append(report.relative_to(report_root).as_posix())
        if code:
            findings.append(Finding("OUTPUT.GUARD_FAILED", f"latex_guard.py failed: {detail}"))
        if active.get("max_sections") is not None:
            code, detail = _run(
                "section_economy_check.py",
                [str(canonical.path), "--max-sections", str(active["max_sections"]), "--markdown"],
            )
            report = report_root / "section_economy_check.md"
            _write_report(report, "Venue Section Economy Check", code, detail)
            generated.append(report.relative_to(report_root).as_posix())
            if code:
                findings.append(Finding("OUTPUT.GUARD_FAILED", f"section_economy_check.py failed: {detail}"))

    if word_requested(active):
        docx_rel = word_relative(active)
        docx = delivery_root / docx_rel
        report = report_root / ("word_report.zh.md" if docx_rel.endswith("zh.docx") else "word_report.md")
        arguments = [
            str(docx), "--markdown", "--output", str(report), "--citation-mode",
            str(active.get("citation_mode") or "numeric"), "--font-policy",
            str(active.get("word_font_policy") or "default"),
        ]
        if canonical.path.suffix.lower() == ".tex":
            arguments.extend(["--tex", str(canonical.path)])
        code, detail = _run("word_guard.py", arguments)
        try:
            existing_detail = report.read_text(encoding="utf-8-sig") if report.is_file() else ""
        except (OSError, UnicodeError):
            existing_detail = ""
        _write_report(
            report,
            "Word Guard",
            code,
            detail,
            existing_detail=existing_detail,
        )
        generated.append(report.relative_to(report_root).as_posix())
        if code:
            findings.append(Finding("OUTPUT.GUARD_FAILED", f"word_guard.py failed: {detail}", docx_rel))

    if package_enabled(active, "translation_package"):
        docx_rel = "translation_zh/paper.zh.docx"
        docx = delivery_root / docx_rel
        report = report_root / "translation_word_report.md"
        arguments = [
            str(docx), "--markdown", "--output", str(report), "--citation-mode",
            str(active.get("citation_mode") or "numeric"), "--font-policy",
            str(active.get("word_font_policy") or "default"),
        ]
        code, detail = _run("word_guard.py", arguments)
        try:
            existing_detail = report.read_text(encoding="utf-8-sig") if report.is_file() else ""
        except (OSError, UnicodeError):
            existing_detail = ""
        _write_report(
            report,
            "Translation Word Guard",
            code,
            detail,
            existing_detail=existing_detail,
        )
        generated.append("translation_word_report.md")
        if code:
            findings.append(Finding("OUTPUT.GUARD_FAILED", f"translation Word guard failed: {detail}", docx_rel))

    expected_reports = set(required_report_relatives(active, canonical.path))
    if set(generated) != expected_reports:
        findings.append(
            Finding(
                "OUTPUT.GUARD_REPORT_SET",
                "output guards did not produce the exact report set required by the output route",
            )
        )
    for relative in sorted(expected_reports):
        if not report_passed(report_root / relative):
            findings.append(
                Finding(
                    "OUTPUT.GUARD_REPORT_INVALID",
                    f"guard report is missing or does not have an unambiguous PASS status: {relative}",
                    relative,
                )
            )
    if findings:
        return GateResult.fail("output", findings)
    return GateResult.pass_("output", generated=generated)
