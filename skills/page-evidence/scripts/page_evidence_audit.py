#!/usr/bin/env python3
"""Audit source-bound page citations; only the controller owns completion."""
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from evidence_contract import (bind_source, cell, digest, load_sources, local_path,
                               locator_ranges, meaningful, parse_evidence, source_digest,
                               source_keys, strict_text, token_present, work_matches)

ZH_PAGE = re.compile(r"第\s*(\d{1,4})(?:\s*[-–—~至]\s*(\d{1,4}))?\s*页")
PP_PAGE = re.compile(r"\bpp?\.\s*(\d{1,4})(?:\s*[-–—]\s*(\d{1,4}))?")
COLON_PAGE = re.compile(r"(?:1[89]|20)\d{2}\s*[:：]\s*(\d{1,4})(?:\s*[-–—]\s*(\d{1,4}))?")

def strip_tex_comments(text: str) -> str:
    return re.sub(r"(?<!\\)%.*", "", text)


def balanced_arg(text: str, start: int) -> tuple[str, int]:
    """Return (content, end_index) of the {...} group starting at text[start]."""
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{" and (i == 0 or text[i - 1] != "\\"):
            depth += 1
        elif text[i] == "}" and text[i - 1] != "\\":
            depth -= 1
            if depth == 0:
                return text[start + 1:i], i
    return text[start + 1:], len(text)


def tex_units(text: str) -> list[tuple[int, str]]:
    """Citation units: every \\footnote/\\footnotetext body and \\bibitem entry."""
    text = strip_tex_comments(text)
    units, covered = [], []
    for m in re.finditer(r"\\footnote(?:text)?\s*(?:\[[^\]]*\])?\s*\{", text):
        body, end = balanced_arg(text, m.end() - 1)
        units.append((text.count("\n", 0, m.start()) + 1, body))
        covered.append((m.start(), end + 1))
    for m in re.finditer(r"\\(?:cite[pt]?|parencite|textcite|footcite|autocite)\*?(?:\s*\[[^\]]*\]){0,2}\s*\{[^}]+\}", text):
        if any(a <= m.start() < b and cited_pages(text[a:b]) for a, b in covered):
            continue
        unit = m.group()
        for value in re.findall(r"\[([^\]]*)\]", unit):
            if re.fullmatch(r"\s*\d+(?:\s*[-–—]\s*\d+)?\s*", value):
                unit += " pp. " + value.strip()
        units.append((text.count("\n", 0, m.start()) + 1, unit))
    bib = re.search(r"\\begin\{thebibliography\}(.*?)\\end\{thebibliography\}",
                    text, re.S)
    if bib:
        base_line = text.count("\n", 0, bib.start()) + 1
        chunk = bib.group(1)
        for m in re.finditer(r"\\bibitem\s*(?:\[[^\]]*\])?\s*\{[^}]*\}(.*?)(?=\\bibitem|\Z)",
                             chunk, re.S):
            units.append((base_line + chunk.count("\n", 0, m.start()), m.group(1)))
    return units


def md_units(text: str) -> list[tuple[int, str]]:
    """Citation units: footnote definitions plus any line with a page pattern."""
    units, seen = [], set()
    for lineno, line in enumerate(text.splitlines(), 1):
        is_footdef = bool(re.match(r"\s*\[\^[^\]]+\]:", line)) or \
            bool(re.match(r"\s*\[\d+\]\s", line))
        has_page = bool(ZH_PAGE.search(line) or PP_PAGE.search(line)
                        or COLON_PAGE.search(line))
        if (is_footdef or has_page) and lineno not in seen:
            seen.add(lineno)
            units.append((lineno, line.strip()))
    return units


def cited_pages(unit: str) -> list[tuple[int, int]]:
    """All (first, last) page ranges pinpointed inside one citation unit."""
    ranges = []
    for rx in (ZH_PAGE, COLON_PAGE, PP_PAGE):
        for m in rx.finditer(unit):
            p1 = int(m.group(1))
            p2 = int(m.group(2)) if m.group(2) else p1
            ranges.append((min(p1, p2), max(p1, p2)))
    return ranges



def manuscript_units(path: Path):
    if path.suffix.lower() == ".docx":
        paragraphs = []
        with zipfile.ZipFile(path) as archive:
            for name in ("word/document.xml", "word/footnotes.xml", "word/endnotes.xml"):
                if name not in archive.namelist():
                    continue
                root = ElementTree.fromstring(archive.read(name))
                for node in root.iter():
                    if node.tag.endswith("}p"):
                        paragraphs.append("".join(child.text or "" for child in node.iter() if child.tag.endswith("}t")))
        return md_units("\n".join(paragraphs))
    if path.suffix.lower() not in {".md", ".tex"}:
        raise ValueError("unsupported canonical manuscript format")
    text = path.read_text(encoding="utf-8-sig")
    return tex_units(text) if path.suffix.lower() == ".tex" else md_units(text)


def page_citations(path: Path):
    return [(line, part, cited_pages(part)) for line, unit in manuscript_units(path)
            for part in re.split(r"[;；]", unit) if cited_pages(part)]


def match_row(unit: str, ranges: list[tuple[int, int]], rows: list[dict],
              sources: list[dict] | None = None) -> tuple[dict | None, float]:
    sources = sources or []
    explicit = [s for s in sources if any(token_present(unit, key) for key in source_keys(s))]
    if len(explicit) > 1:
        return None, 0.0
    matches = []
    for row in rows:
        source = bind_source(row, sources)
        if source is None:
            continue
        identity = (source == explicit[0] if explicit else
                    token_present(unit, row["id"]) or work_matches(unit, source))
        coverage = all(any(a <= lo and hi <= b for a, b in row["pages"]) for lo, hi in ranges)
        kind = "pdf" if re.search(r"PDF\s*(?:第|p\.)", unit, re.I) else "publication"
        if identity and coverage and row.get("locator_kind") == kind:
            matches.append(row)
    return (matches[0], 1.0) if len(matches) == 1 else (None, 0.0)


def row_issues(row: dict, root: Path, sources: list[dict], pdf_cache: dict | None = None):
    issues = []
    source = bind_source(row, sources)
    if source is None:
        return ["source identity is missing or ambiguous"]
    if source_digest(source) != row.get("source_record_sha256"):
        issues.append("source record or edition binding is missing or changed")
    if not work_matches(row.get("work", ""), source):
        issues.append("edition-locked work does not match source metadata")
    if not meaningful(row.get("quote")):
        issues.append("full quote is missing")
    if row.get("status") != "verified":
        issues.append("status must be exactly verified")
    target = local_path(root, row.get("file", ""))
    if target is None or not target.is_file() or not target.stat().st_size:
        issues.append("evidence artifact is missing or outside the workspace")
    elif digest(target) != row.get("artifact_sha256"):
        issues.append("evidence artifact hash is missing or changed")
    original = local_path(root, str(source.get("local_file") or ""))
    if source.get("local_file"):
        if original is None or not original.is_file():
            issues.append("registered source artifact is missing")
        elif (source.get("sha256") or source.get("file_sha256")) and digest(original) != (source.get("sha256") or source.get("file_sha256")):
            issues.append("registered source artifact changed")
    if row.get("locator_kind") not in {"publication", "pdf"} or not row["pages"]:
        issues.append("explicit supported locator kind and page range are required")
    pdf_locator = bool(re.match(r"PDF\s*(?:第|pp?\.)", row.get("locator", ""), re.I))
    if (row.get("locator_kind") == "pdf") != pdf_locator:
        issues.append("locator text and declared locator kind disagree")
    if row.get("tier") == "A":
        if source.get("local_file") and not (source.get("sha256") or source.get("file_sha256")):
            issues.append("page image requires a hash binding for the registered local source")
        if target and target.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}:
            issues.append("Tier A requires a saved page image")
        if not meaningful(row.get("page_basis")):
            issues.append("Tier A requires the observed page and edition basis")
        if source.get("url") and row.get("source") != source["url"]:
            issues.append("page image source URL differs from the registered source")
    elif row.get("tier") == "B":
        if target != original or not target or target.suffix.lower() != ".pdf":
            issues.append("Tier B artifact must be the registered source PDF")
        if local_path(root, row.get("source", "").split("#", 1)[0]) != target:
            issues.append("PDF source locator and evidence artifact disagree")
        if not issues:
            try:
                from pdf_locate import PdfIndex
                cache = pdf_cache if pdf_cache is not None else {}
                if target not in cache:
                    cache[target] = PdfIndex(target)
                idx = cache[target]
                pages = re.fullmatch(r"(\d+)(?:-(\d+))?", row.get("pdf_pages", ""))
                span = re.fullmatch(r"(\d+):(\d+)", row.get("raw_span", ""))
                start = re.match(r"start-page=(\d+):\s*(.+)", row.get("page_basis", ""))
                start_page = int(start[1]) if start else None
                hits = idx.candidates(row["quote"], start_page=start_page)
                selected = [hit for hit in hits if pages and span
                            and (hit["pdf_page_start"], hit["pdf_page_end"]) == (int(pages[1]), int(pages[2] or pages[1]))
                            and (hit["raw_start"], hit["raw_end"]) == (int(span[1]), int(span[2]))]
                if len(selected) != 1 or selected[0]["fidelity"] != "exact_layout":
                    issues.append("full quote, raw span or candidate disambiguation failed")
                else:
                    hit = selected[0]
                    if row["locator_kind"] == "pdf":
                        expected = [(hit["pdf_page_start"], hit["pdf_page_end"])]
                    else:
                        label_basis = re.match(r"labels:\s*(.+)", row.get("page_basis", ""))
                        if not ((label_basis and hit["page_source"] == "labels") or
                                (start and hit["page_source"] == "start-page")):
                            issues.append("publication-page mapping needs its observed basis")
                        values = (hit["printed_start"], hit["printed_end"])
                        expected = [(int(values[0]), int(values[1]))] if all(str(v).isdigit() for v in values) else []
                    if row["pages"] != expected:
                        issues.append("locator differs from the verified PDF position")
            except (OSError, ValueError, ImportError, RuntimeError) as exc:
                issues.append(f"PDF verification unavailable: {exc}")
    else:
        issues.append("only Tier A/B can satisfy pinpoint verification")
    return issues


def verdict(row: dict | None, root: Path | None = None, sources: list[dict] | None = None) -> str:
    if row is None:
        return "NO-EVIDENCE"
    if row.get("tier") == "C":
        return "TRIANGULATED"
    if root is None or row_issues(row, root, sources or []):
        return "UNVERIFIED"
    return "PASS"


def audit(root: Path, manuscript: Path, evidence: Path | None = None):
    evidence = evidence or root / "evidence_bank.md"
    citations = page_citations(manuscript)
    if not citations:
        return {"status": "NOT_APPLICABLE", "findings": [], "issues": [],
                "message": "No applicable page citations in the selected canonical manuscript."}
    rows = parse_evidence(evidence.read_text(encoding="utf-8-sig")) if evidence.is_file() else []
    sources = load_sources(root)
    findings, cache = [], {}
    for line, unit, ranges in citations:
        row, _ = match_row(unit, ranges, rows, sources)
        issues = row_issues(row, root, sources, cache) if row else ["no unique source, edition and locator match"]
        if row:
            quoted = re.findall(r'“([^”]+)”|「([^」]+)」|"([^"]+)"', unit)
            quotes = [next(value for value in values if value) for values in quoted]
            if quotes and any(strict_text(q) != strict_text(row["quote"]) for q in quotes):
                issues.append("manuscript quotation differs from the full evidence quotation")
        findings.append({"line": line, "pages": ranges, "evidence": row["id"] if row else "-",
                         "verdict": ("TRIANGULATED" if row and row["tier"] == "C" else
                                     "NO-EVIDENCE" if row is None else "UNVERIFIED") if issues else "PASS",
                         "issues": issues, "excerpt": unit})
    return {"status": "FAIL" if any(f["verdict"] != "PASS" for f in findings) else "PASS",
            "findings": findings, "issues": []}


def render(result: dict, manuscript: Path):
    lines = ["# Page Evidence Audit", "", f"Status: {result['status']}", "",
             f"Canonical manuscript: {manuscript}", ""]
    if result["status"] == "NOT_APPLICABLE":
        lines.extend([result["message"], ""])
    lines.extend(result.get("issues", []))
    if result["findings"]:
        lines.extend(["| Line | Evidence | Verdict | Reason |", "|---|---|---|---|"])
        for f in result["findings"]:
            lines.append("| " + " | ".join(cell(v) for v in (f["line"], f["evidence"], f["verdict"], "; ".join(f["issues"]))) + " |")
    pending = [f for f in result["findings"] if f["verdict"] != "PASS"]
    if pending:
        lines.extend(["", "## 【VERIFY】", ""])
        lines.extend(f"- Line {f['line']}: {cell(f['excerpt'])}" for f in pending)
    return "\n".join(lines) + "\n"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("outdir", nargs="?", default="paper_rewriting_output", type=Path)
    ap.add_argument("--manuscript", type=Path)
    ap.add_argument("--evidence", type=Path)
    ap.add_argument("--markdown", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()
    manuscript = args.manuscript or args.outdir / "final_paper/main.tex"
    try:
        result = audit(args.outdir, manuscript, args.evidence)
    except (OSError, ValueError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
        result = {"status": "ERROR", "issues": [str(exc)], "findings": []}
    if args.write:
        (args.outdir / "page_evidence_audit.md").write_text(render(result, manuscript), encoding="utf-8")
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.markdown or not args.write:
        print(render(result, manuscript))
    return int(result["status"] == "ERROR" or (args.strict and result["status"] == "FAIL"))


if __name__ == "__main__":
    raise SystemExit(main())
