"""Local manuscript-integrity checks without a parallel artifact state machine."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from ..models import Finding, GateResult


PLACEHOLDER = re.compile(
    r"(?:\bTODO\b|\bTBD\b|\[citation needed\]|\[待补(?:文献|证据|数据)?\]|待填|待定)",
    re.IGNORECASE,
)

# These patterns target revision-process leakage, not scholarship whose object is
# peer review.  A bare occurrence of "reviewer" or "审稿" therefore does not
# fail the manuscript; the term must participate in an author-response formula
# or name an internal writing artifact.
REVIEW_PROCESS_LEAK = re.compile(
    r"(?:"
    r"(?:为|以便)(?:回应|答复|解决|处理)(?:审稿|评审|评议|导师|编辑)(?:人|意见|建议|质疑|要求)?|"
    r"(?:根据|按照)(?:匿名)?(?:审稿|评审|评议|导师|编辑)(?:人)?(?:的)?(?:意见|建议|要求)|"
    r"(?:审稿|评审|评议)(?:人)?(?:指出|认为|建议|要求|质疑)[，,:：]?|"
    r"(?:按|根据)?第\s*[一二三四五六七八九十\d]+\s*轮(?:审稿|评审|评议)?意见"
    r"(?:补充|修改|调整|回应|如下)|"
    r"针对第\s*[一二三四五六七八九十\d]+\s*条(?:意见|建议|评论)|"
    r"在(?:回复|答复|返修)(?:信|说明)?中|"
    r"(?:to|in order to)\s+(?:address|answer|respond to)\s+(?:the\s+)?"
    r"(?:reviewer|referee|editor|peer review|review comment)|"
    r"in response to\s+(?:the\s+)?(?:reviewer|referee|editor|peer review|review comment)|"
    r"(?:reviewer|referee|editor|peer review)\s+"
    r"(?:requested|suggested|asked|commented|recommended|required|advised|noted|raised)|"
    r"(?:as|following)\s+(?:the\s+)?(?:reviewer|referee|editor|peer review)(?:'s)?\s+"
    r"(?:request|suggestion|comment)"
    r")",
    re.IGNORECASE,
)

CONTROL_ARTIFACT_LEAK = re.compile(
    r"(?:\bProsePacket\b|\bcontrol[- ]plane\b|\bwriter[- ]safe view\b|"
    r"\bresponse view\b|\bresponse matrix\b|\breviewer comment\b|"
    r"\bcomment ID\b|\bClaim ID\b|\bEvidence ID\b|"
    r"回复矩阵|评论编号|审稿意见编号|写作者安全视图|控制面)",
    re.IGNORECASE,
)


def _reader_text(path: Path) -> str:
    if path.suffix.lower() == ".docx":
        try:
            with zipfile.ZipFile(path) as archive:
                raw = archive.read("word/document.xml")
            root = ElementTree.fromstring(raw)
            return " ".join(node.text or "" for node in root.iter() if node.tag.endswith("}t"))
        except (OSError, KeyError, zipfile.BadZipFile, ElementTree.ParseError):
            # Format validity remains owned by the output guards. Integrity only
            # scans readable manuscript text and does not invent a second DOCX gate.
            return ""
    try:
        return path.read_text(encoding="utf-8-sig", errors="ignore")
    except OSError:
        return ""


def run(outdir: Path, manuscript: Path, *, write: bool = True) -> GateResult:
    findings: list[Finding] = []
    text = _reader_text(manuscript)
    if text and PLACEHOLDER.search(text):
        findings.append(
            Finding(
                "INTEGRITY.PLACEHOLDER",
                "canonical manuscript contains unresolved placeholder text",
                manuscript.relative_to(outdir).as_posix(),
            )
        )
    if text and REVIEW_PROCESS_LEAK.search(text):
        findings.append(
            Finding(
                "INTEGRITY.REVIEW_PROCESS_LEAK",
                "canonical manuscript contains author-response or review-process language",
                manuscript.relative_to(outdir).as_posix(),
            )
        )
    if text and CONTROL_ARTIFACT_LEAK.search(text):
        findings.append(
            Finding(
                "INTEGRITY.CONTROL_ARTIFACT_LEAK",
                "canonical manuscript exposes an internal writing or review artifact",
                manuscript.relative_to(outdir).as_posix(),
            )
        )
    nested = outdir / "paper_rewriting_output"
    if nested.is_dir():
        findings.append(
            Finding(
                "INTEGRITY.NESTED_ROOT",
                "nested paper_rewriting_output creates competing artifact roots",
                "paper_rewriting_output",
            )
        )
    result = GateResult.fail("audit", findings) if findings else GateResult.pass_("audit")
    if write:
        lines = [
            "# Avereth Integrity Audit",
            "",
            f"Status: {'PASS' if result.ok else 'FAIL'}",
            "",
            f"Canonical manuscript: `{manuscript.relative_to(outdir).as_posix()}`",
        ]
        if findings:
            lines.extend(["", "## Blocking Issues", ""])
            lines.extend(f"- [{item.code}] {item.message}" for item in findings)
        lines.append("")
        (outdir / "integrity_audit.md").write_text("\n".join(lines), encoding="utf-8")
    return result
