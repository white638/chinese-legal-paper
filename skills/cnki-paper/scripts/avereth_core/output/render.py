"""Render staged delivery candidates from one audit-bound manuscript."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from xml.etree import ElementTree
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..artifacts import sha256_file
from ..build.manuscript import ManuscriptSelection
from ..models import Finding, GateResult
from .policy import primary_delivery_relatives, word_relative, word_requested


@dataclass
class RenderOutcome:
    result: GateResult
    deliveries: list[dict[str, Any]] = field(default_factory=list)
    qa_artifacts: list[dict[str, Any]] = field(default_factory=list)
    renderers: list[dict[str, Any]] = field(default_factory=list)


def _which(*names: str) -> str | None:
    for name in names:
        resolved = shutil.which(name)
        if resolved:
            return resolved
    return None


def _run(command: list[str], *, cwd: Path | None = None, timeout: int = 300) -> tuple[int, str]:
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd) if cwd is not None else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=timeout,
            creationflags=flags,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 2, str(exc)
    detail = " ".join((result.stdout + "\n" + result.stderr).split())[-1600:]
    return result.returncode, detail


def _renderer_version(executable: str) -> str:
    code, detail = _run([executable, "--version"], timeout=30)
    return detail[:300] if code == 0 else "version unavailable"


def _valid_docx(path: Path) -> bool:
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
        return {"[Content_Types].xml", "word/document.xml"}.issubset(names)
    except (OSError, zipfile.BadZipFile):
        return False


def _source_text(path: Path) -> str:
    if path.suffix.lower() in {".md", ".tex"}:
        try:
            return path.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            return ""
    if path.suffix.lower() == ".docx":
        try:
            with zipfile.ZipFile(path) as archive:
                root = ElementTree.fromstring(archive.read("word/document.xml"))
        except (OSError, zipfile.BadZipFile, KeyError, ElementTree.ParseError):
            return ""
        return " ".join(node.text or "" for node in root.iter() if node.tag.endswith("}t"))
    return ""


def _language_finding(source: Path, config: dict[str, Any]) -> Finding | None:
    if str(config.get("output_language") or "en").strip().lower() != "zh":
        return None
    text = _source_text(source)
    cjk = len(re.findall(r"[\u3400-\u9fff]", text))
    alphabetic = len(re.findall(r"[A-Za-z\u3400-\u9fff]", text))
    if cjk < 20 or (alphabetic and cjk / alphabetic < 0.10):
        return Finding(
            "OUTPUT.LANGUAGE_MISMATCH",
            "output_language=zh requires a Chinese canonical manuscript; the renderer cannot relabel or invent a translation",
            str(source),
        )
    return None


def _pdf_pages(path: Path) -> int:
    try:
        from pypdf import PdfReader

        return len(PdfReader(str(path)).pages)
    except Exception:
        return 0


def _file_record(root: Path, path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": sha256_file(path),
        "size": path.stat().st_size,
    }


def _normalize_pandoc_quote_fonts(destination: Path, renderers: list[dict[str, Any]]) -> Finding | None:
    """Route curly quotes after Pandoc while preserving direct DOCX copy semantics."""
    scripts_root = Path(__file__).resolve().parents[2]
    scripts_root_text = str(scripts_root)
    if scripts_root_text in sys.path:
        sys.path.remove(scripts_root_text)
    sys.path.insert(0, scripts_root_text)
    try:
        from docx_fixup.docx_normalize import normalize_docx_quote_fonts

        report = normalize_docx_quote_fonts(destination, locale_basis="content")
    except Exception as exc:
        return Finding(
            "OUTPUT.DOCX_QUOTE_NORMALIZE_FAILED",
            f"generated DOCX quote-font normalization failed: {exc}",
            str(destination),
        )
    renderers.append({
        "name": "quote-font-normalizer",
        "version": "2",
        "command_digest": "docx:quote-fonts:context-v2",
        "report": report,
    })
    return None


def _render_docx(source: Path, destination: Path, renderers: list[dict[str, Any]]) -> Finding | None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.suffix.lower() == ".docx":
        shutil.copy2(source, destination)
        renderers.append({"name": "lossless-docx-copy", "version": "1", "command_digest": "copy"})
    else:
        pandoc = _which("pandoc")
        if not pandoc:
            return Finding(
                "OUTPUT.RENDERER_MISSING",
                f"pandoc is required to render {source.suffix.lower()} to DOCX",
                str(source),
            )
        code, detail = _run(
            [pandoc, source.name, "--resource-path", str(source.parent), "-o", str(destination)],
            cwd=source.parent,
        )
        if code != 0:
            return Finding("OUTPUT.RENDER_FAILED", f"pandoc DOCX render failed: {detail}", str(source))
        renderers.append(
            {"name": "pandoc", "version": _renderer_version(pandoc), "command_digest": "pandoc:docx:v1"}
        )
        finding = _normalize_pandoc_quote_fonts(destination, renderers)
        if finding:
            return finding
    if not _valid_docx(destination):
        return Finding("OUTPUT.DOCX_INVALID", "rendered DOCX is not a valid editable Word package", str(destination))
    return None


def _render_tex_pdf(source: Path, destination: Path, renderers: list[dict[str, Any]]) -> Finding | None:
    latexmk = _which("latexmk")
    xelatex = _which("xelatex")
    if not latexmk and not xelatex:
        return Finding("OUTPUT.RENDERER_MISSING", "latexmk or xelatex is required for the requested PDF", str(source))
    with tempfile.TemporaryDirectory(prefix="avereth-tex-render-") as raw_work:
        work = Path(raw_work) / "source"
        shutil.copytree(
            source.parent,
            work,
            ignore=shutil.ignore_patterns(
                ".git",
                ".avereth-output-candidate",
                ".avereth-*.lock",
                "__pycache__",
            ),
        )
        local_source = work / source.name
        if latexmk:
            command = [latexmk, "-xelatex", "-interaction=nonstopmode", "-halt-on-error", local_source.name]
            code, detail = _run(command, cwd=work)
            engine = latexmk
        else:
            command = [xelatex or "xelatex", "-interaction=nonstopmode", "-halt-on-error", local_source.name]
            code, detail = _run(command, cwd=work)
            if code == 0:
                code, detail = _run(command, cwd=work)
            engine = xelatex or "xelatex"
        generated = work / f"{source.stem}.pdf"
        if code != 0 or not generated.is_file():
            return Finding("OUTPUT.RENDER_FAILED", f"TeX PDF render failed: {detail}", str(source))
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(generated, destination)
    renderers.append(
        {"name": Path(engine).name, "version": _renderer_version(engine), "command_digest": "tex:pdf:v1"}
    )
    return None


def _render_pdf(source: Path, destination: Path, renderers: list[dict[str, Any]]) -> Finding | None:
    if source.suffix.lower() == ".tex":
        finding = _render_tex_pdf(source, destination, renderers)
    elif source.suffix.lower() == ".md":
        pandoc = _which("pandoc")
        if not pandoc:
            return Finding("OUTPUT.RENDERER_MISSING", "pandoc is required to render Markdown to PDF", str(source))
        destination.parent.mkdir(parents=True, exist_ok=True)
        code, detail = _run(
            [pandoc, source.name, "--resource-path", str(source.parent), "-o", str(destination)],
            cwd=source.parent,
        )
        finding = None if code == 0 else Finding("OUTPUT.RENDER_FAILED", f"pandoc PDF render failed: {detail}", str(source))
        if finding is None:
            renderers.append({"name": "pandoc", "version": _renderer_version(pandoc), "command_digest": "pandoc:pdf:v1"})
    else:
        return _render_word_preview(source, destination, renderers)
    if finding is None and _pdf_pages(destination) <= 0:
        return Finding("OUTPUT.PDF_INVALID", "rendered PDF is empty or structurally invalid", str(destination))
    return finding


def _render_word_preview(source: Path, destination: Path, renderers: list[dict[str, Any]]) -> Finding | None:
    soffice = _which("soffice", "libreoffice")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if soffice:
        code, detail = _run(
            [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(destination.parent), str(source)]
        )
        generated = destination.parent / f"{source.stem}.pdf"
        if code == 0 and generated.is_file() and generated != destination:
            generated.replace(destination)
        renderer = {"name": Path(soffice).name, "version": _renderer_version(soffice), "command_digest": "office:pdf:v1"}
    elif os.name == "nt" and shutil.which("powershell.exe"):
        script = Path(__file__).with_name("word_render.ps1")
        code, detail = _run(
            [
                shutil.which("powershell.exe") or "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
                "-InputPath",
                str(source),
                "-OutputPath",
                str(destination),
            ]
        )
        renderer = {"name": "Microsoft Word", "version": detail[:200], "command_digest": "word-com:pdf:v1"}
    else:
        return Finding(
            "OUTPUT.RENDERER_MISSING",
            "LibreOffice or Microsoft Word is required for reader-level DOCX rendering QA",
            str(source),
        )
    if code != 0 or _pdf_pages(destination) <= 0:
        return Finding("OUTPUT.RENDER_FAILED", f"Word preview render failed: {detail}", str(source))
    renderers.append(renderer)
    return None


def render_candidate(
    outdir: Path,
    candidate_root: Path,
    canonical: ManuscriptSelection,
    config: dict[str, Any],
) -> RenderOutcome:
    language_issue = _language_finding(canonical.path, config)
    if language_issue:
        return RenderOutcome(GateResult.fail("output", [language_issue]))
    relatives = primary_delivery_relatives(config, canonical.path)
    if not relatives:
        return RenderOutcome(
            GateResult.blocked(
                "output",
                [Finding("OUTPUT.NO_DELIVERABLE", "declare word_output and/or pdf_output explicitly")],
            )
        )
    findings: list[Finding] = []
    renderers: list[dict[str, Any]] = []
    for relative in relatives:
        destination = candidate_root / relative
        if relative.endswith(".docx"):
            finding = _render_docx(canonical.path, destination, renderers)
        else:
            finding = _render_pdf(canonical.path, destination, renderers)
        if finding:
            findings.append(finding)
    qa_artifacts: list[dict[str, Any]] = []
    if not findings and word_requested(config):
        docx = candidate_root / word_relative(config)
        preview = candidate_root / "render_qa" / "word_preview.pdf"
        finding = _render_word_preview(docx, preview, renderers)
        if finding:
            findings.append(finding)
        else:
            record = _file_record(candidate_root, preview)
            record["pages"] = _pdf_pages(preview)
            qa_artifacts.append(record)
    if findings:
        blocked = any(item.code == "OUTPUT.RENDERER_MISSING" for item in findings)
        result = GateResult.blocked("output", findings) if blocked else GateResult.fail("output", findings)
        return RenderOutcome(result, renderers=renderers)
    deliveries = [_file_record(candidate_root, candidate_root / relative) for relative in relatives]
    return RenderOutcome(GateResult.pass_("output"), deliveries, qa_artifacts, renderers)
