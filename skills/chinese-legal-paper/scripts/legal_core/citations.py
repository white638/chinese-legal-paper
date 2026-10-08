"""Working-note formatting and read-only DOCX footnote integrity checks."""
from pathlib import Path
import re
import zipfile
from xml.etree import ElementTree as ET

from .common import LegalError, FILES, read_json
from .validation import check_workspace


def field(record, key):
    value = record.get(key)
    if value is None or value == "" or value == []:
        raise LegalError("CITATION.METADATA_MISSING", f"Working note needs verified canonical field: {key}")
    if not isinstance(value, (str, int)):
        raise LegalError("CITATION.METADATA_TYPE", f"Unsupported canonical field shape: {key}")
    return str(value)


def authors(record):
    value = record.get("authors")
    if not isinstance(value, list) or not value:
        raise LegalError("CITATION.METADATA_MISSING", "Scholarship note requires verified authors")
    names = []
    for author in value:
        if isinstance(author, str) and author.strip():
            names.append(author.strip())
        elif isinstance(author, dict) and isinstance(author.get("name"), str) and author["name"].strip():
            names.append(author["name"].strip())
        else:
            raise LegalError("CITATION.AUTHOR", "Normalize actual author names in the canonical registry")
    return "、".join(names)


def render_notes(outdir):
    result = check_workspace(outdir, stage="build")
    if result["status"] != "PASS":
        raise LegalError("CITATION.NOT_READY", "Fix legal build checks before formatting notes: " +
                         "; ".join(i["code"] for i in result["issues"]))
    outdir = Path(outdir)
    citations = read_json(outdir / FILES["citations"])
    if citations["style"] != "working-footnote-v1":
        raise LegalError("STYLE.MANUAL_REQUIRED", "Apply the supplied journal rules through the existing manuscript/export workflow")
    sources = {s["source_id"]: s for s in read_json(outdir / FILES["sources"])["sources"]}
    records = {s["source_id"]: s for s in read_json(outdir / "reference_materials/literature_registry.json")["sources"]}
    lines = []
    for entry in citations["entries"]:
        record, source = records[entry["source_id"]], sources[entry["source_id"]]
        title = field(record, "title")
        locator = entry["locator"]["label"]
        if source["kind"] in {"case", "case_summary"}:
            case = source["case"]
            label = "数据库案例摘要" if source["kind"] == "case_summary" else case["document_type"]
            note = f"{case['court']}：{title}，{case['case_number']}，{label}，{case['decided_at']}，{locator}"
        elif source["kind"] in {"statute", "regulation", "judicial_interpretation", "policy"}:
            authority, temporal = source["authority"], source["temporal"]
            note = f"《{title}》（{authority['document_number']}，版本 {source['version_id']}），{locator}"
            if temporal.get("promulgated"):
                note += f"，公布于 {temporal['promulgated']}"
        else:
            venue = record.get("journal") or record.get("venue") or record.get("publisher")
            if not isinstance(venue, str) or not venue.strip():
                raise LegalError("CITATION.METADATA_MISSING", "Scholarship note needs journal, venue or publisher")
            note = f"{authors(record)}：《{title}》，{venue}，{field(record, 'year')}，{locator}"
        if entry["mode"] == "secondary":
            original = records[entry["original_source_id"]]
            note = f"原始文献《{field(original, 'title')}》（未直接核阅），转引自：" + note
        if source["access"]["level"] == "partial":
            note += "（仅核对所获片段）"
        if any(c in note for c in "\r\n") or re.search(r"\[\^[^\]]+\]", note):
            raise LegalError("CITATION.UNSAFE_TEXT", "Normalize newlines and embedded footnote markup before rendering")
        lines.append(f"[^{entry['citation_id']}]: {note}。")
    return "\n".join(lines) + "\n"


def audit_docx(path):
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    ident = "{" + ns["w"] + "}id"
    issues = []
    try:
        with zipfile.ZipFile(path) as archive:
            for name in ("word/document.xml", "word/footnotes.xml"):
                if name not in archive.namelist():
                    if name.endswith("document.xml"):
                        raise LegalError("DOCX.INVALID", "DOCX document.xml is missing")
                    continue
                if archive.getinfo(name).file_size > 20 * 1024 * 1024:
                    raise LegalError("DOCX.TOO_LARGE", "Footnote audit XML exceeds its bounded size")
            document = ET.fromstring(archive.read("word/document.xml"))
            refs = [e.get(ident) for e in document.findall(".//w:footnoteReference", ns)]
            definitions = []
            if "word/footnotes.xml" in archive.namelist():
                notes = ET.fromstring(archive.read("word/footnotes.xml"))
                definitions = [e.get(ident) for e in notes.findall("w:footnote", ns)
                               if e.get(ident, "").isdigit() and int(e.get(ident)) > 0]
            if set(refs) != set(definitions):
                issues.append("Footnote references and definitions differ")
            if len(definitions) != len(set(definitions)):
                issues.append("Duplicate footnote definitions")
            if not refs:
                issues.append("No native DOCX footnotes found")
            for element in document.findall(".//w:t", ns):
                if re.search(r"\[\^CIT-[^\]]+\]", element.text or ""):
                    issues.append("Unconverted Markdown citation marker remains in DOCX")
                    break
    except (OSError, zipfile.BadZipFile, ET.ParseError):
        raise LegalError("DOCX.INVALID", "Unable to parse DOCX footnote XML") from None
    return {"status": "FAIL" if issues else "PASS", "reference_count": len(refs),
            "definition_count": len(definitions), "issues": issues,
            "scope": "native footnote structure only; source accuracy and page layout require separate checks"}
