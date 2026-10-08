"""Build and validate a staged Chinese translation package.

The controller never pretends that rendering is translation. A separate,
editable Chinese source must be declared in the workflow configuration; this
module checks its language and stable citation tokens, renders it, and binds it
to the audited source manuscript.
"""

from __future__ import annotations

import json
import re
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from ..artifacts import sha256_file
from ..build.manuscript import ManuscriptSelection
from ..models import Finding, GateResult
from .policy import package_enabled
from .render import (
    RenderOutcome,
    _file_record,
    _pdf_pages,
    _render_docx,
    _render_word_preview,
    _source_text,
)


SOURCE_SUFFIXES = {".md", ".tex", ".docx"}
DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
URL_RE = re.compile(r"https?://[^\s)\]>]+", re.IGNORECASE)
NUMERIC_CITATION_RE = re.compile(r"\[(?:\d+[\s,;\-–—]*)+\]")
AUTHOR_NAME_PATTERN = r"[^\W\d_](?:[^\W\d_]|['’\-]){0,40}"
AUTHOR_YEAR_PAREN_RE = re.compile(r"[（(]([^()（）\n]{1,240})[)）]")
AUTHOR_YEAR_PAIR_RE = re.compile(
    rf"\b(?P<author>{AUTHOR_NAME_PATTERN})"
    rf"(?:\s+(?:et\s+al\.?|and\s+{AUTHOR_NAME_PATTERN}|&\s*{AUTHOR_NAME_PATTERN}))?"
    r"\s*(?P<separator>[,，]?)\s*(?P<year>(?:19|20)\d{2}[a-z]?)\b",
    re.IGNORECASE,
)
AUTHOR_YEAR_NARRATIVE_RE = re.compile(
    rf"\b(?P<author>{AUTHOR_NAME_PATTERN})"
    rf"(?:\s+(?:et\s+al\.?|and\s+{AUTHOR_NAME_PATTERN}|&\s*{AUTHOR_NAME_PATTERN}))?"
    r"\s*[（(]\s*(?P<year>(?:19|20)\d{2}[a-z]?)\s*[)）]",
    re.IGNORECASE,
)
MARKDOWN_FOOTNOTE_RE = re.compile(r"\[\^([^\]\s]+)\]")
LATEX_FOOTNOTE_RE = re.compile(r"\\footnote(?:\[[^\]]*\])?\s*\{")
MARKDOWN_FOOTNOTE_DEFINITION_RE = re.compile(
    r"(?m)^\[\^([^\]\s]+)\]:[ \t]*(.*(?:\n(?: {2,4}|\t).*)*)"
)
LATEX_CITE_RE = re.compile(
    r"\\(?:cite|citep|citet|parencite|textcite|autocite)\*?(?:\[[^\]]*\]){0,2}\{([^{}]+)\}",
    re.IGNORECASE,
)
PLACEHOLDER_RE = re.compile(
    r"(?:\bTODO\b|\bTBD\b|\bPLACEHOLDER\b|\bVERIFY\b|待填|待定|占位|待核)",
    re.IGNORECASE,
)
UNIT_KINDS = ("section", "table", "figure", "footnote", "appendix")
MONTH_NAMES = frozenset({
    "jan", "january", "feb", "february", "mar", "march", "apr", "april",
    "may", "jun", "june", "jul", "july", "aug", "august", "sep", "sept",
    "september", "oct", "october", "nov", "november", "dec", "december",
})
NON_AUTHOR_YEAR_WORDS = MONTH_NAMES | frozenset({
    "the", "a", "an", "from", "to", "in", "of", "for", "and", "or",
    "pre", "post", "before", "after", "since", "until", "between", "during",
    "spring", "summer", "autumn", "fall", "winter", "survey", "report", "data",
})


def _safe_source(outdir: Path, config: dict[str, Any]) -> tuple[Path | None, Finding | None]:
    raw = str(config.get("translation_source") or "").strip()
    if not raw:
        return None, Finding(
            "OUTPUT.TRANSLATION_SOURCE_REQUIRED",
            "translation_package=zh requires an explicit editable translation_source",
        )
    candidate = (outdir / raw).resolve()
    try:
        candidate.relative_to(outdir.resolve())
    except ValueError:
        return None, Finding(
            "OUTPUT.TRANSLATION_SOURCE_PATH",
            "translation_source must stay inside the workspace",
            raw,
        )
    if candidate.suffix.lower() not in SOURCE_SUFFIXES or not candidate.is_file() or candidate.stat().st_size <= 0:
        return None, Finding(
            "OUTPUT.TRANSLATION_SOURCE_INVALID",
            "translation_source must be a non-empty .md, .tex, or .docx file",
            raw,
        )
    return candidate, None


def input_bindings(outdir: Path, config: dict[str, Any]) -> list[dict[str, Any]]:
    if not package_enabled(config, "translation_package"):
        return []
    source, _ = _safe_source(outdir, config)
    records = [{
        "role": "translation_source",
        "path": source.relative_to(outdir.resolve()).as_posix() if source is not None else str(config.get("translation_source") or ""),
        "sha256": sha256_file(source) if source is not None else "",
    }]
    raw_coverage = str(config.get("translation_coverage_source") or "").strip()
    coverage = (outdir / raw_coverage).resolve() if raw_coverage else None
    valid_coverage = False
    if coverage is not None:
        try:
            coverage.relative_to(outdir.resolve())
            valid_coverage = coverage.is_file()
        except ValueError:
            valid_coverage = False
    records.append({
        "role": "translation_coverage",
        "path": raw_coverage,
        "sha256": sha256_file(coverage) if valid_coverage and coverage is not None else "",
    })
    return records


def _coverage_contract(
    outdir: Path,
    config: dict[str, Any],
    canonical: ManuscriptSelection,
    translated: Path,
) -> tuple[dict[str, Any], list[Finding]]:
    raw = str(config.get("translation_coverage_source") or "").strip()
    path = (outdir / raw).resolve() if raw else outdir / "__missing_translation_coverage__"
    findings: list[Finding] = []
    try:
        path.relative_to(outdir.resolve())
    except ValueError:
        return {}, [Finding("OUTPUT.TRANSLATION_COVERAGE_PATH", "translation_coverage_source must stay inside the workspace", raw)]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}, [Finding("OUTPUT.TRANSLATION_COVERAGE_REQUIRED", "translation_coverage_source must be a readable JSON contract", raw)]
    if not isinstance(payload, dict):
        return {}, [Finding("OUTPUT.TRANSLATION_COVERAGE_REQUIRED", "translation coverage must contain one JSON object", raw)]
    if payload.get("schema_version") != "avereth-translation-coverage/v1" or payload.get("status") != "confirmed":
        findings.append(Finding(
            "OUTPUT.TRANSLATION_COVERAGE_STATUS",
            "translation coverage must use avereth-translation-coverage/v1 with status=confirmed",
            raw,
        ))
    if payload.get("source_sha256") != canonical.sha256:
        findings.append(Finding("OUTPUT.TRANSLATION_COVERAGE_SOURCE", "translation coverage does not bind the audited source SHA256", raw))
    if payload.get("translation_sha256") != sha256_file(translated):
        findings.append(Finding("OUTPUT.TRANSLATION_COVERAGE_TRANSLATION", "translation coverage does not bind the Chinese source SHA256", raw))
    if not str(payload.get("reviewed_by") or "").strip():
        findings.append(Finding("OUTPUT.TRANSLATION_COVERAGE_REVIEWER", "translation coverage requires an actual reviewer identity", raw))
    units = payload.get("units")
    if not isinstance(units, list) or not units:
        findings.append(Finding(
            "OUTPUT.TRANSLATION_COVERAGE_UNITS",
            "translation coverage requires an exact units list for sections, tables, figures, footnotes, and appendices",
            raw,
        ))
    else:
        declared: Counter[str] = Counter()
        for index, item in enumerate(units):
            kind = str(item.get("kind") or "") if isinstance(item, dict) else ""
            if not isinstance(item, dict) or any(
                not str(item.get(key) or "").strip()
                for key in ("source_anchor", "translation_anchor")
            ) or kind not in UNIT_KINDS or str(item.get("status") or "").strip().lower() != "final":
                findings.append(Finding(
                    "OUTPUT.TRANSLATION_COVERAGE_UNIT",
                    f"translation coverage unit {index + 1} must name a supported kind, source/translation anchors, and status=final",
                    raw,
                ))
            else:
                declared[kind] += 1
        source_units = _structural_unit_counts(canonical.path)
        translation_units = _structural_unit_counts(translated)
        if source_units != translation_units:
            findings.append(Finding(
                "OUTPUT.TRANSLATION_STRUCTURE_PARITY",
                f"source/translation structural unit counts differ: source={source_units}, translation={translation_units}",
                raw,
            ))
        expected = Counter({kind: count for kind, count in source_units.items() if count})
        if declared != expected:
            findings.append(Finding(
                "OUTPUT.TRANSLATION_COVERAGE_EXACT_SET",
                f"coverage units must exactly map the source unit set: expected={dict(expected)}, declared={dict(declared)}",
                raw,
            ))
        payload["verified_unit_counts"] = dict(expected)
    return payload, findings


def _structural_unit_counts(path: Path) -> dict[str, int]:
    counts = {kind: 0 for kind in UNIT_KINDS}
    suffix = path.suffix.lower()
    text = _source_text(path)
    if suffix == ".md":
        headings = re.findall(r"(?m)^#{1,6}\s+(.+?)\s*$", text)
        counts["appendix"] = sum(1 for heading in headings if re.match(r"(?i)^(?:appendix|附录)\b", heading.strip()))
        counts["section"] = max(0, len(headings) - counts["appendix"])
        counts["table"] = len(re.findall(r"(?m)^\s*\|?.+\|.+\n\s*\|?\s*:?-{3,}", text))
        counts["figure"] = len(re.findall(r"!\[[^\]]*\]\([^)]*\)", text))
        counts["footnote"] = len(list(MARKDOWN_FOOTNOTE_DEFINITION_RE.finditer(text)))
    elif suffix == ".tex":
        appendix_at = text.find(r"\appendix")
        sections = list(re.finditer(r"\\(?:sub)*section\*?\s*\{", text))
        counts["appendix"] = sum(1 for match in sections if appendix_at >= 0 and match.start() > appendix_at)
        counts["section"] = len(sections) - counts["appendix"]
        if appendix_at >= 0 and not counts["appendix"]:
            counts["appendix"] = 1
        counts["table"] = len(re.findall(r"\\begin\s*\{table\*?\}", text))
        counts["figure"] = len(re.findall(r"\\begin\s*\{figure\*?\}", text))
        counts["footnote"] = len(_latex_footnote_bodies(text))
    elif suffix == ".docx":
        try:
            with zipfile.ZipFile(path) as archive:
                document = ElementTree.fromstring(archive.read("word/document.xml"))
                footnotes = ElementTree.fromstring(archive.read("word/footnotes.xml")) if "word/footnotes.xml" in archive.namelist() else None
        except (OSError, zipfile.BadZipFile, KeyError, ElementTree.ParseError):
            return counts
        headings: list[str] = []
        for paragraph in document.iter():
            if not paragraph.tag.endswith("}p"):
                continue
            style = next((node for node in paragraph.iter() if node.tag.endswith("}pStyle")), None)
            style_value = next((value for key, value in (style.attrib.items() if style is not None else []) if key.endswith("}val")), "")
            if style_value.lower().startswith("heading"):
                headings.append("".join(node.text or "" for node in paragraph.iter() if node.tag.endswith("}t")))
        counts["appendix"] = sum(1 for heading in headings if re.match(r"(?i)^(?:appendix|附录)\b", heading.strip()))
        counts["section"] = max(0, len(headings) - counts["appendix"])
        counts["table"] = sum(1 for node in document.iter() if node.tag.endswith("}tbl"))
        counts["figure"] = sum(1 for node in document.iter() if node.tag.endswith("}drawing"))
        if footnotes is not None:
            counts["footnote"] = sum(
                1 for node in footnotes if node.tag.endswith("}footnote")
                and int(next((value for key, value in node.attrib.items() if key.endswith("}id")), "-1")) >= 0
            )
    if not counts["section"]:
        counts["section"] = 1
    return counts


def _author_year_identity(author: str, year: str) -> str:
    return f"author-year:{author.casefold()}:{year.casefold()}"


def _normalized_author_word(value: str) -> str:
    return value.casefold().strip("-'’–—")


def _author_year_tokens(
    text: str,
    allowed_no_comma: set[str] | None = None,
) -> Counter[str]:
    values: Counter[str] = Counter()
    allowed = allowed_no_comma or set()
    for parenthetical in AUTHOR_YEAR_PAREN_RE.finditer(text):
        for match in AUTHOR_YEAR_PAIR_RE.finditer(parenthetical.group(1)):
            identity = _author_year_identity(match.group("author"), match.group("year"))
            if not match.group("separator") and identity not in allowed:
                continue
            values[identity] += 1
    for match in AUTHOR_YEAR_NARRATIVE_RE.finditer(text):
        values[_author_year_identity(match.group("author"), match.group("year"))] += 1
    return values


def _ambiguous_no_comma_author_year(
    text: str,
    allowed_no_comma: set[str] | None = None,
) -> list[str]:
    allowed = allowed_no_comma or set()
    ambiguous: set[str] = set()
    for parenthetical in AUTHOR_YEAR_PAREN_RE.finditer(text):
        for match in AUTHOR_YEAR_PAIR_RE.finditer(parenthetical.group(1)):
            if match.group("separator"):
                continue
            identity = _author_year_identity(match.group("author"), match.group("year"))
            author = _normalized_author_word(match.group("author"))
            if identity not in allowed and author not in NON_AUTHOR_YEAR_WORDS:
                ambiguous.add(identity)
    return sorted(ambiguous)


def _registry_author_year_identities(outdir: Path) -> set[str]:
    try:
        registry = json.loads(
            (outdir / "reference_materials" / "literature_registry.json").read_text(encoding="utf-8-sig")
        )
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return set()
    if not isinstance(registry, dict):
        return set()
    identities: set[str] = set()
    for source in registry.get("sources") or []:
        if not isinstance(source, dict):
            continue
        year = str(source.get("publication_year") or source.get("year") or "").strip()
        if not re.fullmatch(r"(?:19|20)\d{2}[a-z]?", year, re.IGNORECASE):
            continue
        authors = source.get("authors") or []
        if not isinstance(authors, list):
            authors = [authors]
        for raw_author in authors:
            author = str(raw_author or "").strip()
            if not author:
                continue
            surname = author.split(",", 1)[0].strip() if "," in author else author.split()[-1]
            if surname:
                identities.add(_author_year_identity(surname, year))
    return identities


def _latex_footnote_bodies(text: str) -> list[str]:
    bodies: list[str] = []
    for marker in LATEX_FOOTNOTE_RE.finditer(text):
        start = marker.end() - 1
        depth = 0
        for index in range(start, len(text)):
            character = text[index]
            if character == "{" and (index == 0 or text[index - 1] != "\\"):
                depth += 1
            elif character == "}" and (index == 0 or text[index - 1] != "\\"):
                depth -= 1
                if depth == 0:
                    bodies.append(text[start + 1:index])
                    break
    return bodies


def _citation_identities(text: str) -> Counter[str]:
    values: Counter[str] = Counter()
    values.update(match.group(0).rstrip(".,;，。；").lower() for match in DOI_RE.finditer(text))
    values.update(match.group(0).rstrip(".,;，。；").lower() for match in URL_RE.finditer(text))
    values.update(_author_year_tokens(text))
    for match in LATEX_CITE_RE.finditer(text):
        for key in match.group(1).split(","):
            if key.strip():
                values[f"cite-key:{key.strip().lower()}"] += 1
    return values


def _unverifiable_footnotes(text: str) -> list[str]:
    unresolved: list[str] = []
    for match in MARKDOWN_FOOTNOTE_DEFINITION_RE.finditer(text):
        if not _citation_identities(match.group(2)):
            unresolved.append(f"markdown:{match.group(1)}")
    for index, body in enumerate(_latex_footnote_bodies(text), start=1):
        if not _citation_identities(body):
            unresolved.append(f"latex:{index}")
    return unresolved


def _stable_tokens(
    text: str,
    citation_mode: str,
    allowed_no_comma: set[str] | None = None,
) -> Counter[str]:
    values: Counter[str] = Counter()
    values.update(match.group(0).rstrip(".,;，。；").lower() for match in DOI_RE.finditer(text))
    values.update(match.group(0).rstrip(".,;，。；").lower() for match in URL_RE.finditer(text))
    if citation_mode == "numeric":
        values.update("numeric:" + re.sub(r"\s+", "", match.group(0)) for match in NUMERIC_CITATION_RE.finditer(text))
    elif citation_mode == "author_year":
        values.update(_author_year_tokens(text, allowed_no_comma))
    elif citation_mode == "footnote":
        values.update(f"footnote:markdown:{match.group(1).lower()}" for match in MARKDOWN_FOOTNOTE_RE.finditer(text))
        for match in MARKDOWN_FOOTNOTE_DEFINITION_RE.finditer(text):
            footnote_id = match.group(1).lower()
            for identity, count in _citation_identities(match.group(2)).items():
                values[f"footnote:markdown:{footnote_id}:{identity}"] += count
        latex_bodies = _latex_footnote_bodies(text)
        values.update("footnote:latex" for _ in latex_bodies)
        for index, body in enumerate(latex_bodies, start=1):
            for identity, count in _citation_identities(body).items():
                values[f"footnote:latex:{index}:{identity}"] += count
    return values


def _language_and_parity_findings(
    source: Path,
    translated: Path,
    citation_mode: str,
    allowed_no_comma: set[str] | None = None,
) -> tuple[list[Finding], dict[str, Any]]:
    original_text = _source_text(source)
    translated_text = _source_text(translated)
    findings: list[Finding] = []
    original_cjk = len(re.findall(r"[\u3400-\u9fff]", original_text))
    original_alpha = len(re.findall(r"[A-Za-z\u3400-\u9fff]", original_text))
    if original_cjk >= 20 and original_alpha and original_cjk / original_alpha >= 0.10:
        findings.append(Finding(
            "OUTPUT.TRANSLATION_SOURCE_LANGUAGE",
            "translation_package=zh requires an English audited source; use output_language=zh for a Chinese primary manuscript",
            str(source),
        ))
    cjk = len(re.findall(r"[\u3400-\u9fff]", translated_text))
    alphabetic = len(re.findall(r"[A-Za-z\u3400-\u9fff]", translated_text))
    if cjk < 20 or (alphabetic and cjk / alphabetic < 0.10):
        findings.append(Finding(
            "OUTPUT.TRANSLATION_LANGUAGE",
            "the declared translation source does not contain enough Chinese text",
            str(translated),
        ))
    if PLACEHOLDER_RE.search(translated_text):
        findings.append(Finding(
            "OUTPUT.TRANSLATION_PLACEHOLDER",
            "translation source contains unresolved placeholders or verification markers",
            str(translated),
        ))
    original_tokens = _stable_tokens(original_text, citation_mode, allowed_no_comma)
    translated_tokens = _stable_tokens(translated_text, citation_mode, allowed_no_comma)
    if citation_mode == "author_year":
        ambiguous = sorted(set(
            _ambiguous_no_comma_author_year(original_text, allowed_no_comma)
            + _ambiguous_no_comma_author_year(translated_text, allowed_no_comma)
        ))
        if ambiguous:
            findings.append(Finding(
                "OUTPUT.TRANSLATION_CITATION_IDENTITY_REQUIRED",
                "no-comma author-year candidates must match an author/year identity in "
                "literature_registry.json before translation parity can be verified: "
                + ", ".join(ambiguous[:8]),
                str(translated),
            ))
    if citation_mode == "footnote" and (
        len(_latex_footnote_bodies(original_text)) != len(list(LATEX_FOOTNOTE_RE.finditer(original_text)))
        or len(_latex_footnote_bodies(translated_text)) != len(list(LATEX_FOOTNOTE_RE.finditer(translated_text)))
    ):
        findings.append(Finding(
            "OUTPUT.TRANSLATION_FOOTNOTE_UNVERIFIABLE",
            "a LaTeX footnote body could not be parsed reliably for citation-identity comparison",
            str(translated),
        ))
    if citation_mode == "footnote":
        unresolved = _unverifiable_footnotes(original_text)
        if unresolved:
            findings.append(Finding(
                "OUTPUT.TRANSLATION_FOOTNOTE_UNVERIFIABLE",
                "source footnotes lack machine-stable DOI, URL, author-year, or citation-key identities: "
                + ", ".join(unresolved[:8])
                + "; add explicit stable citation identities before translation packaging",
                str(source),
            ))
    missing_counts = original_tokens - translated_tokens
    unexpected_counts = translated_tokens - original_tokens
    missing_tokens = sorted(
        f"{token} x{count}" if count > 1 else token
        for token, count in missing_counts.items()
    )
    unexpected_tokens = sorted(
        f"{token} x{count}" if count > 1 else token
        for token, count in unexpected_counts.items()
    )
    if missing_tokens or unexpected_tokens:
        differences: list[str] = []
        if missing_tokens:
            differences.append("omitted: " + ", ".join(missing_tokens[:8]))
        if unexpected_tokens:
            differences.append("unexpected: " + ", ".join(unexpected_tokens[:8]))
        findings.append(Finding(
            "OUTPUT.TRANSLATION_CITATION_PARITY",
            f"translation must preserve the exact stable DOI, URL, and {citation_mode} citation identity multiset; "
            + "; ".join(differences),
            str(translated),
        ))
    original_length = len(re.sub(r"\s+", "", original_text))
    translated_length = len(re.sub(r"\s+", "", translated_text))
    ratio = translated_length / original_length if original_length else 0.0
    if not original_length or ratio < 0.35 or ratio > 3.5:
        findings.append(Finding(
            "OUTPUT.TRANSLATION_COVERAGE",
            f"translation/source text-length ratio {ratio:.2f} is outside the conservative review range 0.35–3.50",
            str(translated),
        ))
    metrics = {
        "source_characters": original_length,
        "translation_characters": translated_length,
        "length_ratio": round(ratio, 4),
        "citation_mode": citation_mode,
        "stable_tokens": sum(original_tokens.values()),
        "missing_stable_tokens": missing_tokens,
        "unexpected_stable_tokens": unexpected_tokens,
        "cjk_characters": cjk,
        "source_cjk_characters": original_cjk,
    }
    return findings, metrics


def build_translation_package(
    outdir: Path,
    candidate_root: Path,
    canonical: ManuscriptSelection,
    config: dict[str, Any],
) -> RenderOutcome:
    if not package_enabled(config, "translation_package"):
        return RenderOutcome(GateResult.pass_("output"))
    if str(config.get("translation_package") or "").strip().lower() != "zh":
        return RenderOutcome(GateResult.fail("output", [Finding(
            "OUTPUT.TRANSLATION_MODE",
            "translation_package must be none or zh",
        )]))
    source, source_issue = _safe_source(outdir, config)
    if source_issue or source is None:
        return RenderOutcome(GateResult.blocked("output", [source_issue] if source_issue else []))
    if source.resolve() == canonical.path.resolve():
        return RenderOutcome(GateResult.fail("output", [Finding(
            "OUTPUT.TRANSLATION_DISTINCT_SOURCE",
            "translation_source must be a separately reviewed Chinese source, not the audited source relabelled",
            str(source),
        )]))
    citation_mode = str(config.get("citation_mode") or "numeric").strip().lower()
    if citation_mode == "footnote" and canonical.path.suffix.lower() == ".docx":
        return RenderOutcome(GateResult.blocked("output", [Finding(
            "OUTPUT.TRANSLATION_FOOTNOTE_UNVERIFIABLE",
            "footnote citation parity cannot be verified from a DOCX canonical source; provide an auditable Markdown/TeX canonical source",
            canonical.relative_path,
        )]))
    findings, metrics = _language_and_parity_findings(
        canonical.path,
        source,
        citation_mode,
        _registry_author_year_identities(outdir) if citation_mode == "author_year" else None,
    )
    coverage, coverage_findings = _coverage_contract(outdir, config, canonical, source)
    findings.extend(coverage_findings)
    if findings:
        if any(item.code == "OUTPUT.TRANSLATION_FOOTNOTE_UNVERIFIABLE" for item in findings):
            return RenderOutcome(GateResult.blocked("output", findings))
        return RenderOutcome(GateResult.fail("output", findings))

    renderers: list[dict[str, Any]] = []
    docx = candidate_root / "translation_zh" / "paper.zh.docx"
    issue = _render_docx(source, docx, renderers)
    if issue:
        status = GateResult.blocked if issue.code == "OUTPUT.RENDERER_MISSING" else GateResult.fail
        return RenderOutcome(status("output", [issue]), renderers=renderers)
    preview = candidate_root / "render_qa" / "translation_preview.pdf"
    issue = _render_word_preview(docx, preview, renderers)
    if issue:
        status = GateResult.blocked if issue.code == "OUTPUT.RENDERER_MISSING" else GateResult.fail
        return RenderOutcome(status("output", [issue]), renderers=renderers)

    package = candidate_root / "translation_zh"
    manifest_path = package / "translation_manifest.json"
    coverage_path = package / "translation_coverage.md"
    manifest = {
        "schema_version": "avereth-translation-package/v1",
        "status": "PASS",
        "audited_source": canonical.as_dict(),
        "translation_source": {
            "path": source.relative_to(outdir.resolve()).as_posix(),
            "sha256": sha256_file(source),
        },
        "delivery": "translation_zh/paper.zh.docx",
        "metrics": metrics,
        "coverage_source": {
            "path": str(config.get("translation_coverage_source") or ""),
            "sha256": sha256_file(outdir / str(config.get("translation_coverage_source") or "")),
        },
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    coverage_path.write_text(
        "# Translation Coverage\n\nStatus: PASS\n\n"
        f"- Audited source: `{canonical.relative_path}`\n"
        f"- Translation source: `{manifest['translation_source']['path']}`\n"
        f"- Semantic coverage reviewed by: `{coverage.get('reviewed_by')}`\n"
        f"- Confirmed structural-unit mappings: {len(coverage.get('units') or [])}\n"
        f"- Text-length ratio: {metrics['length_ratio']}\n"
        f"- Stable citation tokens retained: {metrics['stable_tokens']}\n",
        encoding="utf-8",
    )
    report = candidate_root / "reports" / "translation_guard.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        "# Translation Guard\n\nStatus: PASS\n\n"
        "Chinese-language, placeholder, coverage, and stable citation-token checks passed.\n",
        encoding="utf-8",
    )
    qa_record = _file_record(candidate_root, preview)
    qa_record["pages"] = _pdf_pages(preview)
    deliveries = [
        _file_record(candidate_root, docx),
        _file_record(candidate_root, coverage_path),
        _file_record(candidate_root, manifest_path),
    ]
    return RenderOutcome(GateResult.pass_("output"), deliveries, [qa_record], renderers)
