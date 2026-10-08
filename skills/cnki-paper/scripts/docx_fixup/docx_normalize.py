#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""docx_normalize.py — 中文期刊投稿稿 OOXML 级规范化/修复。

与 tex2docx 正交：tex2docx 从 LaTeX **从零生成** docx；本模块对**任意已有
docx**（Word/WPS 另存、tex2docx 产物、协作回稿）做投稿格式修复，直接操作解包后的
WordprocessingML，不依赖 python-docx（它会抹掉我们关心的元素顺序与脚注细节）。

核心设计：**每次改完都按 ECMA-376 规定的子元素顺序重排**（pPr/rPr/边框/blip），
让"每步过 schema 校验"成为构造性保证，而不是事后祈祷。

风险分层（见 --all 与各显式开关）：
  低风险（默认集）       ：fonts / quote-fonts / footnotes / indent / wps / 末尾排序
  显式字符改写           ：smart-quotes
  破坏性（需显式开启）   ：headings(去重号) / citations(上标+合并+移位) / tables(三线表化) / grayscale

用法：
  python docx_normalize.py <in.docx> [out.docx] [开关...]
  python docx_normalize.py <in.docx> --check          # 只校验不变量，不写文件
  python docx_normalize.py --sanitize "题目: a/b.docx"  # 只输出合法文件名

开关：--all --fonts --quote-fonts --smart-quotes --headings --citations
      --footnotes --tables --grayscale --indent --wps
      --quotes 是 quote-fonts + smart-quotes 的兼容别名（省略全部开关时使用低风险默认集）

详细规则与自动/手动边界见 references/docx-format-fixes.md。
"""
from __future__ import annotations

import argparse
import copy
import os
import re
import sys
import tempfile
import unicodedata
import zipfile
from pathlib import Path

from lxml import etree

# --------------------------------------------------------------------------- #
# 命名空间
# --------------------------------------------------------------------------- #
NS = {
    "w":   "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "a":   "http://schemas.openxmlformats.org/drawingml/2006/main",
    "wp":  "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "r":   "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
}


def qn(tag: str) -> str:
    """'w:rFonts' -> '{http://...}rFonts'"""
    prefix, local = tag.split(":", 1)
    return "{%s}%s" % (NS[prefix], local)


def local(el) -> str:
    """元素的本地名（去命名空间）；非元素节点返回 ''。"""
    if not isinstance(getattr(el, "tag", None), str):
        return ""
    return etree.QName(el).localname


# --------------------------------------------------------------------------- #
# ECMA-376 子元素规范顺序（按本地名）。改完任何容器后用 reorder_children 重排，
# 保证 w:ind 在 w:jc 之前、边框 top/left/bottom/right 等 schema 约束恒成立。
# --------------------------------------------------------------------------- #
PPR_ORDER = [
    "pStyle", "keepNext", "keepLines", "pageBreakBefore", "framePr",
    "widowControl", "numPr", "suppressLineNumbers", "pBdr", "shd", "tabs",
    "suppressAutoHyphens", "kinsoku", "wordWrap", "overflowPunct",
    "topLinePunct", "autoSpaceDE", "autoSpaceDN", "bidi", "adjustRightInd",
    "snapToGrid", "spacing", "ind", "contextualSpacing", "mirrorIndents",
    "suppressOverlap", "jc", "textDirection", "textAlignment",
    "textboxTightWrap", "outlineLvl", "divId", "cnfStyle", "rPr", "sectPr",
    "pPrChange",
]
RPR_ORDER = [
    "rStyle", "rFonts", "b", "bCs", "i", "iCs", "caps", "smallCaps", "strike",
    "dstrike", "outline", "shadow", "emboss", "imprint", "noProof",
    "snapToGrid", "vanish", "webHidden", "color", "spacing", "w", "kern",
    "position", "sz", "szCs", "highlight", "u", "effect", "bdr", "shd",
    "fitText", "vertAlign", "rtl", "cs", "em", "lang", "eastAsianLayout",
    "specVanish", "oMath", "rPrChange",
]
# CT_TblBorders / CT_TcBorders：用户要求 top/left/bottom/right；含 start/end 别名与内边框
BORDER_ORDER = [
    "top", "start", "left", "bottom", "end", "right",
    "insideH", "insideV", "tl2br", "tr2bl",
]
# CT_Blip 效果子元素顺序（仅列我们会碰的）
BLIP_ORDER = [
    "alphaBiLevel", "alphaCeiling", "alphaFloor", "alphaInv", "alphaMod",
    "alphaModFix", "alphaRepl", "biLevel", "blur", "clrChange", "clrRepl",
    "duotone", "fillOverlay", "grayscl", "hsl", "lum", "tint",
]


def reorder_children(parent, order: list[str]) -> None:
    """按 order 给出的本地名顺序稳定重排 parent 的子元素；未列出的保持原相对次序并排后。"""
    if parent is None:
        return
    idx = {name: i for i, name in enumerate(order)}
    children = list(parent)
    decorated = sorted(
        enumerate(children),
        key=lambda pair: (idx.get(local(pair[1]), len(order)), pair[0]),
    )
    for _, ch in decorated:
        parent.append(ch)  # append 会先脱离再挂到末尾，从而实现重排


# --------------------------------------------------------------------------- #
# 低层 helper
# --------------------------------------------------------------------------- #
def _first_child(parent, qname):
    return parent.find(qname)


def ensure_first(parent, qname):
    """确保 parent 的第一个子元素是 qname（如 w:pPr 之于 w:p、w:rPr 之于 w:r）。"""
    el = parent.find(qname)
    if el is None:
        el = etree.SubElement(parent, qname)
    parent.remove(el)
    parent.insert(0, el)
    return el


def get_rpr(run):
    return ensure_first(run, qn("w:rPr"))


def get_ppr(p):
    return ensure_first(p, qn("w:pPr"))


def get_or_make(parent, qname):
    el = parent.find(qname)
    if el is None:
        el = etree.SubElement(parent, qname)
    return el


def paragraph_has_drawing(p) -> bool:
    """段落是否含图形/嵌入对象（w:drawing / w:object / w:pict）。"""
    for tag in ("w:drawing", "w:object", "w:pict"):
        if p.find(".//" + qn(tag)) is not None:
            return True
    return False


def clear_runs(p) -> bool:
    """清空段落内的 w:r。**致命坑**：含 w:drawing 的段绝不能 clear——会丢图。
    含图形时拒绝清空并返回 False；否则清空并返回 True。"""
    if paragraph_has_drawing(p):
        return False
    for r in p.findall(qn("w:r")):
        p.remove(r)
    return True


# --------------------------------------------------------------------------- #
# 文本/标点常量
# --------------------------------------------------------------------------- #
# 弯引号位于 General Punctuation；其字体槽由 run 级 w:hint 决定。同一个字符既可用于
# 中文也可用于英文，必须先按成对语境判定，再把引号拆成独立 run。
CURVED_QUOTES = frozenset("“”‘’")
OPEN_TO_CLOSE = {"“": "”", "‘": "’"}
CLOSE_TO_OPEN = {value: key for key, value in OPEN_TO_CLOSE.items()}
HAN_RE = re.compile(r"[㐀-鿿豈-﫿]")
LATIN_RE = re.compile(r"[A-Za-z]")
TEXT_PART_RE = re.compile(
    r"^word/(?:document|footnotes|endnotes|comments|header\d+|footer\d+)\.xml$"
)
SAFE_RUN_CHILDREN = {qn("w:rPr"), qn("w:t")}
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"


def text_nodes(scope):
    """遍历 scope 下所有 w:t 元素（按文档顺序）。"""
    return scope.iter(qn("w:t"))


# --------------------------------------------------------------------------- #
# T1 字体：补齐 w:eastAsia（只补不覆盖）
# --------------------------------------------------------------------------- #
def ensure_eastasia_fonts(document, styles, default_cjk: str = "SimSun") -> int:
    """凡 w:rFonts 设了 ascii/hAnsi 却没 eastAsia 的，补 eastAsia=宋体（不覆盖既有值）。
    同时给 styles.xml 的 docDefaults 补 eastAsia。"""
    n = 0
    targets = [document]
    if styles is not None:
        targets.append(styles)
    for root in targets:
        for rf in root.iter(qn("w:rFonts")):
            has_latin = rf.get(qn("w:ascii")) or rf.get(qn("w:hAnsi"))
            if has_latin and not rf.get(qn("w:eastAsia")):
                rf.set(qn("w:eastAsia"), default_cjk)
                n += 1
    if styles is not None:
        # docDefaults/rPrDefault/rPr/rFonts 补 eastAsia（WPS 另存常丢）
        dd = styles.find(qn("w:docDefaults"))
        if dd is not None:
            rpr = dd.find(qn("w:rPrDefault") + "/" + qn("w:rPr"))
            if rpr is not None:
                rf = rpr.find(qn("w:rFonts"))
                if rf is not None and not rf.get(qn("w:eastAsia")):
                    rf.set(qn("w:eastAsia"), default_cjk)
                    n += 1
    return n


# --------------------------------------------------------------------------- #
# T2 引号字体：按显式语言/成对语境路由；字符改写由 smart_quotes 单独负责
# --------------------------------------------------------------------------- #
def _set_run_hint(run, locale: str) -> bool:
    """把一个引号 run 路由到正确字体槽；zh=eastAsia，en=default。"""
    desired = "eastAsia" if locale == "zh" else "default"
    rpr = get_rpr(run)
    rf = get_or_make(rpr, qn("w:rFonts"))
    if rf.get(qn("w:hint")) == desired:
        return False
    rf.set(qn("w:hint"), desired)
    reorder_children(rpr, RPR_ORDER)
    return True


def _run_text(run) -> str:
    return "".join(t.text or "" for t in run.findall(qn("w:t")))


def _is_safe_text_run(run) -> bool:
    children = list(run)
    return bool(run.findall(qn("w:t"))) and all(child.tag in SAFE_RUN_CHILDREN for child in children)


def _explicit_run_locale(run) -> str | None:
    rpr = run.find(qn("w:rPr"))
    lang = None if rpr is None else rpr.find(qn("w:lang"))
    if lang is None:
        return None
    values = [lang.get(qn("w:val")), lang.get(qn("w:eastAsia")), lang.get(qn("w:bidi"))]
    for value in values:
        normalized = (value or "").strip().lower().replace("_", "-")
        if normalized.startswith(("zh", "cmn", "yue")):
            return "zh"
        if normalized.startswith("en"):
            return "en"
    return None


def _paragraph_projection(paragraph):
    """Return visible text plus a character-to-(run, run offset) map."""
    text: list[str] = []
    refs: list[tuple[object, int]] = []
    offsets: dict[int, int] = {}
    for node in paragraph.iter():
        if node.tag != qn("w:t"):
            continue
        run = node.getparent()
        while run is not None and run is not paragraph and run.tag != qn("w:r"):
            run = run.getparent()
        if run is None or run is paragraph:
            continue
        offset = offsets.get(id(run), 0)
        value = node.text or ""
        for index, char in enumerate(value):
            text.append(char)
            refs.append((run, offset + index))
        offsets[id(run)] = offset + len(value)
    return "".join(text), refs


def _is_latin(char: str) -> bool:
    return bool(char and LATIN_RE.fullmatch(char))


def _is_apostrophe(text: str, index: int) -> bool:
    if text[index] != "’":
        return False
    previous = text[index - 1] if index else ""
    following = text[index + 1] if index + 1 < len(text) else ""
    if _is_latin(previous) and _is_latin(following):
        return True
    if text[index] == "’" and _is_latin(previous) and (not following or following.isspace() or following in ",.;:!?)]}”"):
        return True
    tail = text[index + 1:index + 6]
    return text[index] == "’" and bool(re.match(r"(?:\d{2}|\d{4})s\b", tail, re.IGNORECASE))


def _is_internal_apostrophe(text: str, index: int) -> bool:
    if text[index] != "’":
        return False
    previous = text[index - 1] if index else ""
    following = text[index + 1] if index + 1 < len(text) else ""
    return (
        (_is_latin(previous) and _is_latin(following))
        or bool(re.match(r"(?:\d{2}|\d{4})s\b", text[index + 1:index + 6], re.IGNORECASE))
    )


def _dominant_locale(text: str) -> str | None:
    cjk = len(HAN_RE.findall(text))
    latin = len(LATIN_RE.findall(text))
    strong = cjk + latin
    if not strong:
        return None
    if cjk and cjk / strong >= 0.70:
        return "zh"
    if latin and latin / strong >= 0.70:
        return "en"
    return None


def _quote_locale(text: str, refs, start: int, end: int, locale_basis: str) -> str | None:
    quote_locales = {
        locale for index in (start, end)
        if (locale := _explicit_run_locale(refs[index][0])) is not None
    }
    if len(quote_locales) == 1:
        return next(iter(quote_locales))
    if len(quote_locales) > 1:
        return None
    inner_locales = {
        locale for run, _ in refs[start + 1:end]
        if (locale := _explicit_run_locale(run)) is not None
    }
    if len(inner_locales) == 1:
        return next(iter(inner_locales))
    if len(inner_locales) > 1:
        return None
    if locale_basis == "host":
        return _dominant_locale(text)
    return _dominant_locale(text[start + 1:end]) or _dominant_locale(text)


def _quote_plan(paragraph, locale_basis: str = "content"):
    text, refs = _paragraph_projection(paragraph)
    decisions: dict[tuple[int, int], tuple[str, str]] = {}
    ambiguous: list[int] = []
    stacks: dict[str, list[int]] = {char: [] for char in OPEN_TO_CLOSE}
    paired: set[int] = set()
    for index, char in enumerate(text):
        if _is_internal_apostrophe(text, index):
            run, offset = refs[index]
            decisions[(id(run), offset)] = ("en", "apostrophe")
            paired.add(index)
        elif char in CLOSE_TO_OPEN and stacks[CLOSE_TO_OPEN[char]]:
            opening = CLOSE_TO_OPEN[char]
            start = stacks[opening].pop()
            locale = _quote_locale(text, refs, start, index, locale_basis)
            if locale:
                for position in (start, index):
                    run, offset = refs[position]
                    decisions[(id(run), offset)] = (locale, "quote")
                    paired.add(position)
            else:
                ambiguous.extend((start, index))
                paired.update((start, index))
        elif _is_apostrophe(text, index):
            run, offset = refs[index]
            decisions[(id(run), offset)] = ("en", "apostrophe")
            paired.add(index)
        elif char in OPEN_TO_CLOSE:
            stacks[char].append(index)
        elif char in CLOSE_TO_OPEN:
            ambiguous.append(index)
            paired.add(index)
    for positions in stacks.values():
        ambiguous.extend(positions)
        paired.update(positions)
    for index, char in enumerate(text):
        if char in CURVED_QUOTES and index not in paired:
            ambiguous.append(index)
    return text, refs, decisions, sorted(set(ambiguous))


def _clone_text_run_shell(run):
    clone = copy.deepcopy(run)
    for child in list(clone):
        if child.tag != qn("w:rPr"):
            clone.remove(child)
    return clone


def _replace_run_with_segments(run, segments: list[tuple[str, str | None]]) -> None:
    parent = run.getparent()
    index = parent.index(run)
    parent.remove(run)
    for offset, (text, locale) in enumerate(segments):
        new_run = _clone_text_run_shell(run)
        if locale:
            _set_run_hint(new_run, locale)
        node = etree.SubElement(new_run, qn("w:t"))
        node.text = text
        if text != text.strip():
            node.set(XML_SPACE, "preserve")
        parent.insert(index + offset, new_run)


def normalize_quote_fonts(scope, *, locale_basis: str = "content") -> dict[str, int]:
    """Route paired curly quotes and English apostrophes without changing characters.

    Only pure-text runs are split. Runs containing fields, drawings, breaks, tabs, references,
    or other non-text children are preserved and reported.
    """
    report = {
        "quotes_routed": 0,
        "apostrophes_routed": 0,
        "runs_split": 0,
        "ambiguous_skipped": 0,
        "unsafe_runs_skipped": 0,
    }
    for paragraph in scope.iter(qn("w:p")):
        _, refs, decisions, ambiguous = _quote_plan(paragraph, locale_basis)
        report["ambiguous_skipped"] += len(ambiguous)
        by_run: dict[int, dict[int, tuple[str, str]]] = {}
        run_by_id: dict[int, object] = {}
        for (run_id, offset), decision in decisions.items():
            by_run.setdefault(run_id, {})[offset] = decision
        for run, _ in refs:
            run_by_id[id(run)] = run
        for run_id, offsets in by_run.items():
            run = run_by_id[run_id]
            if not _is_safe_text_run(run):
                report["unsafe_runs_skipped"] += len(offsets)
                continue
            value = _run_text(run)
            if len(value) == 1 and 0 in offsets:
                locale, kind = offsets[0]
                if _set_run_hint(run, locale):
                    report[f"{kind}s_routed"] += 1
                continue
            segments: list[tuple[str, str | None]] = []
            plain: list[str] = []
            for index, char in enumerate(value):
                decision = offsets.get(index)
                if decision:
                    if plain:
                        segments.append(("".join(plain), None))
                        plain = []
                    locale, kind = decision
                    segments.append((char, locale))
                    report[f"{kind}s_routed"] += 1
                else:
                    plain.append(char)
            if plain:
                segments.append(("".join(plain), None))
            _replace_run_with_segments(run, segments)
            report["runs_split"] += 1
    return report


def audit_quote_fonts(scope, *, locale_basis: str = "content") -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    for paragraph_index, paragraph in enumerate(scope.iter(qn("w:p")), start=1):
        _, refs, decisions, ambiguous = _quote_plan(paragraph, locale_basis)
        for _ in ambiguous:
            warnings.append(f"WORD.QUOTE_LOCALE_AMBIGUOUS paragraph={paragraph_index}")
        run_texts = {id(run): _run_text(run) for run, _ in refs}
        for (run_id, offset), (locale, kind) in decisions.items():
            run = next(run for run, _ in refs if id(run) == run_id)
            expected = "eastAsia" if locale == "zh" else "default"
            rpr = run.find(qn("w:rPr"))
            rfonts = None if rpr is None else rpr.find(qn("w:rFonts"))
            actual = None if rfonts is None else rfonts.get(qn("w:hint"))
            code = "WORD.APOSTROPHE_FONT_MISMATCH" if kind == "apostrophe" else "WORD.QUOTE_FONT_MISMATCH"
            if actual != expected:
                errors.append(
                    f"{code} paragraph={paragraph_index} char={run_texts[run_id][offset]!r} "
                    f"expected={expected} actual={actual or '(missing)'}"
                )
            if len(run_texts[run_id]) != 1:
                errors.append(
                    f"WORD.QUOTE_RUN_NOT_SPLIT paragraph={paragraph_index} run={run_texts[run_id]!r}"
                )
    return list(dict.fromkeys(errors)), list(dict.fromkeys(warnings))


def audit_docx_quote_fonts(path: Path, *, locale_basis: str = "content") -> tuple[list[str], list[str]]:
    package = Docx(path)
    errors: list[str] = []
    warnings: list[str] = []
    for name in package.text_part_names():
        part_errors, part_warnings = audit_quote_fonts(package.tree(name), locale_basis=locale_basis)
        errors.extend(f"{name}: {item}" for item in part_errors)
        warnings.extend(f"{name}: {item}" for item in part_warnings)
    return errors, warnings


def _straight_apostrophe(text: str, index: int) -> bool:
    previous = text[index - 1] if index else ""
    following = text[index + 1] if index + 1 < len(text) else ""
    if _is_latin(previous) and _is_latin(following):
        return True
    if _is_latin(previous) and (not following or following.isspace() or following in ",.;:!?)]}"):
        return len(re.search(r"[A-Za-z]+$", text[:index]).group(0)) > 1
    return bool(re.match(r"(?:\d{2}|\d{4})s\b", text[index + 1:index + 6], re.IGNORECASE))


def _smart_quote_pairs(text: str, char: str, excluded: set[int]) -> list[tuple[int, int]]:
    pairs: list[tuple[int, int]] = []
    opening: int | None = None
    open_context = "\"'“‘([{<：，。！？；、"
    close_context = "\"'”’)]}>，。！？；：、,.!?;:"
    for index, value in enumerate(text):
        if value != char or index in excluded:
            continue
        previous = text[index - 1] if index else ""
        following = text[index + 1] if index + 1 < len(text) else ""
        can_open = not previous or previous.isspace() or previous in open_context
        can_close = not following or following.isspace() or following in close_context
        if opening is None and can_open:
            opening = index
        elif opening is not None and can_close:
            pairs.append((opening, index))
            opening = None
    return pairs


def smart_quotes(document) -> int:
    """Conservatively curl paired ASCII quotes and English apostrophes.

    Prime/measurement-like and unmatched marks are preserved. Font routing is intentionally
    separate and is performed only when quote_fonts is also requested.
    """
    changed = 0
    for p in document.iter(qn("w:p")):
        text, refs = _paragraph_projection(p)
        apostrophes = {index for index, char in enumerate(text) if char == "'" and _straight_apostrophe(text, index)}
        replacements: dict[int, str] = {index: "’" for index in apostrophes}
        for char, opening, closing in (('"', "“", "”"), ("'", "‘", "’")):
            for start, end in _smart_quote_pairs(text, char, apostrophes):
                replacements[start] = opening
                replacements[end] = closing
        by_node: dict[int, tuple[object, list[str]]] = {}
        node_offsets: dict[int, int] = {}
        for position, (run, run_offset) in enumerate(refs):
            if position not in replacements:
                continue
            running = 0
            for node in run.findall(qn("w:t")):
                length = len(node.text or "")
                if running <= run_offset < running + length:
                    key = id(node)
                    if key not in by_node:
                        by_node[key] = (node, list(node.text or ""))
                        node_offsets[key] = running
                    chars = by_node[key][1]
                    chars[run_offset - node_offsets[key]] = replacements[position]
                    changed += 1
                    break
                running += length
        for node, chars in by_node.values():
            node.text = "".join(chars)
    return changed


# --------------------------------------------------------------------------- #
# T3 标题：去重号（一）（一） + 可选字号层级
# --------------------------------------------------------------------------- #
DUP_NUM_RE = re.compile(r"^（([一二三四五六七八九十百零\d]+)）（\1）")


def _para_text(p) -> str:
    return "".join(t.text or "" for t in p.findall(".//" + qn("w:t")))


def _set_para_text(p, new_text) -> bool:
    """把段落首个 w:t 设为 new_text 并清空其余 w:t。含图形的段拒绝改（返回 False）。"""
    if paragraph_has_drawing(p):
        return False
    ts = p.findall(".//" + qn("w:t"))
    if not ts:
        return False
    ts[0].text = new_text
    if new_text and (new_text[:1] == " " or new_text[-1:] == " "):
        ts[0].set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    for extra in ts[1:]:
        extra.text = ""
    return True


def dedup_heading_numbering(document, heading_sizes: dict[int, int] | None = None) -> int:
    """折叠标题里重复的 （一）（一） → （一）；可选按级设字号（half-point）。"""
    n = 0
    for p in document.iter(qn("w:p")):
        txt = _para_text(p)
        m = DUP_NUM_RE.match(txt)
        if m:
            new = DUP_NUM_RE.sub("（%s）" % m.group(1), txt, count=1)
            if _set_para_text(p, new):
                n += 1
        if heading_sizes:
            lvl = _heading_level(p)
            if lvl and lvl in heading_sizes:
                _apply_size(p, heading_sizes[lvl])
    return n


def _heading_level(p):
    ppr = p.find(qn("w:pPr"))
    if ppr is None:
        return None
    st = ppr.find(qn("w:pStyle"))
    if st is None:
        return None
    val = st.get(qn("w:val")) or ""
    m = re.search(r"(?:Heading|标题\s*)(\d)", val)
    return int(m.group(1)) if m else None


def _apply_size(p, half_points: int) -> None:
    for run in p.findall(qn("w:r")):
        rpr = get_rpr(run)
        for tag in ("w:sz", "w:szCs"):
            el = get_or_make(rpr, qn(tag))
            el.set(qn("w:val"), str(half_points))
        reorder_children(rpr, RPR_ORDER)


# --------------------------------------------------------------------------- #
# T4 引注/注释：上标 + 合并连续序号 + 移到标点后（文本节点局部，跨 run 不处理）
# --------------------------------------------------------------------------- #
BRACKET_GROUP_RE = re.compile(r"(?:\[\d+\])(?:\[\d+\])+")  # 连续两个及以上 [n]
SINGLE_BRACKET_RE = re.compile(r"\[(\d+)\]")
# 引注在句末标点之前 → 移到其后
CITE_BEFORE_PUNCT_RE = re.compile(r"(\[\d+(?:[-,]\d+)*\])([。！？，、；：”’）》])")


def _compress_nums(nums: list[int]) -> str:
    """[8,9,10,12] -> '8-10,12'（GB/T 7714 连续段用 -，跳号用 ,）。"""
    nums = sorted(set(nums))
    parts, i = [], 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        if j > i:
            parts.append("%d-%d" % (nums[i], nums[j]))
        else:
            parts.append(str(nums[i]))
        i = j + 1
    return ",".join(parts)


def merge_citations(document) -> int:
    """[8][9]→[8-9]，[8][9][10][12]→[8-10,12]；并把引注移到句末标点之后。"""
    n = 0
    for t in text_nodes(document):
        s = t.text
        if not s:
            continue
        new = s

        def _merge(m):
            nums = [int(x) for x in re.findall(r"\d+", m.group(0))]
            return "[" + _compress_nums(nums) + "]"

        new2 = BRACKET_GROUP_RE.sub(_merge, new)
        new2 = CITE_BEFORE_PUNCT_RE.sub(r"\2\1", new2)
        if new2 != s:
            t.text = new2
            n += 1
    return n


def superscript_citations(document) -> int:
    """把 run 文本里的 [n]/[n-m,k] 拆出来设为上标（vertAlign=superscript）。
    只处理单个 w:t 内的引注；保留前后文本。含图形段跳过。"""
    n = 0
    for p in list(document.iter(qn("w:p"))):
        if paragraph_has_drawing(p):
            continue
        for run in list(p.findall(qn("w:r"))):
            ts = run.findall(qn("w:t"))
            if len(ts) != 1 or ts[0].text is None:
                continue
            s = ts[0].text
            if not SINGLE_BRACKET_RE.search(s) and "[" not in s:
                continue
            cite_re = re.compile(r"\[\d+(?:[-,]\d+)*\]")
            if not cite_re.search(s):
                continue
            # 已经是上标则跳过
            rpr = run.find(qn("w:rPr"))
            if rpr is not None and rpr.find(qn("w:vertAlign")) is not None:
                continue
            pieces = []
            last = 0
            for m in cite_re.finditer(s):
                if m.start() > last:
                    pieces.append(("plain", s[last:m.start()]))
                pieces.append(("cite", m.group(0)))
                last = m.end()
            if last < len(s):
                pieces.append(("plain", s[last:]))
            if not any(k == "cite" for k, _ in pieces):
                continue
            new_runs = []
            for kind, text in pieces:
                nr = _clone_run_shell(run)
                if kind == "cite":
                    rp = get_rpr(nr)
                    va = get_or_make(rp, qn("w:vertAlign"))
                    va.set(qn("w:val"), "superscript")
                    reorder_children(rp, RPR_ORDER)
                te = etree.SubElement(nr, qn("w:t"))
                te.text = text
                if text != text.strip():
                    te.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
                new_runs.append(nr)
            idx = list(p).index(run)
            p.remove(run)
            for off, nr in enumerate(new_runs):
                p.insert(idx + off, nr)
            n += 1
    return n


def _clone_run_shell(run):
    """复制 run 的 rPr（不含 w:t），用于拆分。"""
    nr = etree.Element(qn("w:r"))
    rpr = run.find(qn("w:rPr"))
    if rpr is not None:
        import copy
        nr.append(copy.deepcopy(rpr))
    return nr


# --------------------------------------------------------------------------- #
# T5 脚注：id 顺序 == 引用顺序（致命坑），并按 id 重排 footnotes.xml
# --------------------------------------------------------------------------- #
def reorder_footnotes(document, footnotes) -> int:
    """重排脚注：按 document.xml 中 w:footnoteReference 的出现顺序重编 id（跳过
    separator/continuationSeparator），同步改引用与定义，并按新 id 重排定义元素。
    **致命坑**：成稿后引用顺序里的 id 必须 == footnotes.xml 中定义的 id 顺序。"""
    if footnotes is None:
        return 0
    refs = list(document.iter(qn("w:footnoteReference")))
    if not refs:
        return 0

    fn_defs = footnotes.findall(qn("w:footnote"))
    special_ids, special_nums = set(), []
    for fn in fn_defs:
        if fn.get(qn("w:type")) in ("separator", "continuationSeparator"):
            fid = fn.get(qn("w:id"))
            special_ids.add(fid)
            try:
                special_nums.append(int(fid))
            except (TypeError, ValueError):
                pass
    start = (max(special_nums) + 1) if special_nums else 1
    if start < 1:
        start = 1

    # 引用顺序里的唯一 id（首次出现）
    order_ids, seen = [], set()
    for el in refs:
        fid = el.get(qn("w:id"))
        if fid not in seen and fid not in special_ids:
            seen.add(fid)
            order_ids.append(fid)

    mapping, nxt = {}, start
    for oid in order_ids:
        mapping[oid] = str(nxt)
        nxt += 1
    # 定义了却没被引用的孤儿脚注：排在后面
    for fn in fn_defs:
        oid = fn.get(qn("w:id"))
        if oid in special_ids or oid in mapping:
            continue
        mapping[oid] = str(nxt)
        nxt += 1

    for el in refs:
        oid = el.get(qn("w:id"))
        if oid in mapping:
            el.set(qn("w:id"), mapping[oid])
    for fn in fn_defs:
        oid = fn.get(qn("w:id"))
        if oid in mapping:
            fn.set(qn("w:id"), mapping[oid])

    def _idkey(fn):
        try:
            return int(fn.get(qn("w:id")))
        except (TypeError, ValueError):
            return 0

    for fn in sorted(footnotes.findall(qn("w:footnote")), key=_idkey):
        footnotes.append(fn)  # 按新 id 升序重排（separator 的负/零 id 自然在前）
    return len(mapping)


# --------------------------------------------------------------------------- #
# T7 三线表：删表样式/底纹/行级 tblPrEx/单元格边框；表级仅留 top+bottom；首行下边线
# --------------------------------------------------------------------------- #
def _set_border(borders_el, side, sz="8", val="single", color="auto"):
    el = get_or_make(borders_el, qn("w:" + side))
    el.set(qn("w:val"), val)
    el.set(qn("w:sz"), sz)
    el.set(qn("w:space"), "0")
    el.set(qn("w:color"), color)


def make_three_line_tables(document) -> int:
    """把表格规整为三线表：清表样式/底纹/行级 tblPrEx，清单元格内框，表级仅 top/bottom，
    首行（表头）加下边线。边框子元素顺序经 reorder 保证 top/left/bottom/right。"""
    n = 0
    for tbl in document.iter(qn("w:tbl")):
        tblpr = tbl.find(qn("w:tblPr"))
        if tblpr is not None:
            for tag in ("w:tblStyle", "w:shd", "w:tblBorders"):
                for e in tblpr.findall(qn(tag)):
                    tblpr.remove(e)
            tb = etree.SubElement(tblpr, qn("w:tblBorders"))
            _set_border(tb, "top", sz="12")
            _set_border(tb, "bottom", sz="12")
            reorder_children(tb, BORDER_ORDER)
            reorder_children(tblpr, [
                "tblStyle", "tblpPr", "tblOverlap", "bidiVisual", "tblStyleRowBandSize",
                "tblStyleColBandSize", "tblW", "jc", "tblCellSpacing", "tblInd",
                "tblBorders", "shd", "tblLayout", "tblCellMar", "tblLook", "tblCaption",
                "tblDescription", "tblPrChange",
            ])
        rows = tbl.findall(qn("w:tr"))
        for ri, tr in enumerate(rows):
            trpr = tr.find(qn("w:trPr"))
            # 删行级 tblPrEx（覆盖表属性、常带边框/底纹残留）
            for ex in tr.findall(qn("w:tblPrEx")):
                tr.remove(ex)
            for tc in tr.findall(qn("w:tc")):
                tcpr = tc.find(qn("w:tcPr"))
                if tcpr is None:
                    continue
                for e in tcpr.findall(qn("w:shd")):
                    tcpr.remove(e)
                for e in tcpr.findall(qn("w:tcBorders")):
                    tcpr.remove(e)
                # 表头行：单元格加下边线
                if ri == 0:
                    tcb = etree.SubElement(tcpr, qn("w:tcBorders"))
                    _set_border(tcb, "bottom", sz="8")
                    reorder_children(tcb, BORDER_ORDER)
                reorder_children(tcpr, [
                    "cnfStyle", "tcW", "gridSpan", "hMerge", "vMerge", "tcBorders",
                    "shd", "noWrap", "tcMar", "textDirection", "tcFitText",
                    "vAlign", "hideMark", "headers", "tcPrChange",
                ])
        n += 1
    return n


# --------------------------------------------------------------------------- #
# T8 图：彩图→灰度（a:grayscl）；含图段去 lineRule=exact（否则裁成一条线）
# --------------------------------------------------------------------------- #
def grayscale_images(document) -> int:
    """给每个 a:blip 插入 <a:grayscl/>（渲染期转灰度，不动图像字节，可逆）。"""
    n = 0
    for blip in document.iter(qn("a:blip")):
        if blip.find(qn("a:grayscl")) is not None:
            continue
        etree.SubElement(blip, qn("a:grayscl"))
        reorder_children(blip, BLIP_ORDER)
        n += 1
    return n


def fix_drawing_line_spacing(document) -> int:
    """含 w:drawing 的段若设了 spacing/@w:lineRule=exact，会把内联图裁成一行高——改为 auto。"""
    n = 0
    for p in document.iter(qn("w:p")):
        if not paragraph_has_drawing(p):
            continue
        ppr = p.find(qn("w:pPr"))
        if ppr is None:
            continue
        sp = ppr.find(qn("w:spacing"))
        if sp is not None and sp.get(qn("w:lineRule")) == "exact":
            sp.set(qn("w:lineRule"), "auto")
            if sp.get(qn("w:line")):
                del sp.attrib[qn("w:line")]
            n += 1
    return n


# --------------------------------------------------------------------------- #
# T9 段落：首行缩进 twips → firstLineChars（2 字）；ind 排到 jc 前由 reorder 保证
# --------------------------------------------------------------------------- #
def firstline_chars(document, add_missing: bool = False) -> int:
    """正文段把 w:ind/@w:firstLine(twips) 换成 @w:firstLineChars=200（2 字）。
    add_missing=True 时给无缩进的正文段补 2 字缩进（不动标题/列表/含图段）。"""
    n = 0
    for p in document.iter(qn("w:p")):
        if _heading_level(p) or paragraph_has_drawing(p):
            continue
        ppr = p.find(qn("w:pPr"))
        if ppr is None:
            if not add_missing:
                continue
            ppr = get_ppr(p)
        ind = ppr.find(qn("w:ind"))
        if ind is not None and ind.get(qn("w:firstLine")):
            del ind.attrib[qn("w:firstLine")]
            ind.set(qn("w:firstLineChars"), "200")
            n += 1
        elif add_missing and ind is None:
            ind = etree.SubElement(ppr, qn("w:ind"))
            ind.set(qn("w:firstLineChars"), "200")
            n += 1
        reorder_children(ppr, PPR_ORDER)
    return n


# --------------------------------------------------------------------------- #
# 末尾排序兜底：全篇 pPr/rPr/边框按规范顺序重排（schema 安全的构造性保证）
# --------------------------------------------------------------------------- #
def reorder_all(document) -> int:
    n = 0
    for ppr in document.iter(qn("w:pPr")):
        reorder_children(ppr, PPR_ORDER)
        n += 1
    for rpr in document.iter(qn("w:rPr")):
        reorder_children(rpr, RPR_ORDER)
    for tag in ("w:tblBorders", "w:tcBorders", "w:pBdr"):
        for b in document.iter(qn(tag)):
            reorder_children(b, BORDER_ORDER)
    return n


# --------------------------------------------------------------------------- #
# T11 WPS 修复：styles.xml docDefaults 还原（eastAsia 在 ensure_eastasia_fonts 里）
#                此处仅做最保守的兜底，深度修复见文档。
# --------------------------------------------------------------------------- #
def fix_wps_styles(styles) -> int:
    if styles is None:
        return 0
    n = 0
    # WPS 偶尔把 docDefaults 丢空；确保结构存在不在此越权重建，仅交由字体补齐。
    return n


# --------------------------------------------------------------------------- #
# T12 文件名：非法 ASCII → 全角；NFC 规范化；去尾部空格/点
# --------------------------------------------------------------------------- #
_ILLEGAL_MAP = {
    '"': "＂", "/": "／", ":": "：", "*": "＊", "?": "？",
    "<": "＜", ">": "＞", "|": "｜", "\\": "＼",
}


def sanitize_filename(name: str) -> str:
    """Windows 非法字符 " / : * ? < > | \\ → 全角；NFC 规范化；去首尾空白与尾部点。"""
    name = unicodedata.normalize("NFC", name)
    name = "".join(_ILLEGAL_MAP.get(ch, ch) for ch in name)
    name = "".join(ch for ch in name if ord(ch) >= 32)  # 去控制字符
    name = name.strip().rstrip(" .")
    return name or "untitled"


# --------------------------------------------------------------------------- #
# 不变量校验（轻量"schema 校验"：检查我们承诺的不变量，而非完整 XSD）
# --------------------------------------------------------------------------- #
def validate(document, footnotes, styles) -> list[str]:
    issues = []
    # 1) 容器子元素顺序
    def _check_order(elem, order, where):
        idx = {name: i for i, name in enumerate(order)}
        last = -1
        for ch in elem:
            ln = local(ch)
            if ln in idx:
                if idx[ln] < last:
                    issues.append("%s 子元素顺序违规：%s" % (where, ln))
                last = max(last, idx[ln])

    for ppr in document.iter(qn("w:pPr")):
        _check_order(ppr, PPR_ORDER, "w:pPr")
    for rpr in document.iter(qn("w:rPr")):
        _check_order(rpr, RPR_ORDER, "w:rPr")
    for tag in ("w:tblBorders", "w:tcBorders"):
        for b in document.iter(qn(tag)):
            _check_order(b, BORDER_ORDER, tag)

    # 2) 脚注 id 顺序 == 引用顺序
    if footnotes is not None:
        special = {fn.get(qn("w:id")) for fn in footnotes.findall(qn("w:footnote"))
                   if fn.get(qn("w:type")) in ("separator", "continuationSeparator")}
        ref_ids = []
        for el in document.iter(qn("w:footnoteReference")):
            fid = el.get(qn("w:id"))
            if fid not in special and fid not in ref_ids:
                ref_ids.append(fid)
        def_ids = [fn.get(qn("w:id")) for fn in footnotes.findall(qn("w:footnote"))
                   if fn.get(qn("w:id")) not in special]
        try:
            ref_int = [int(x) for x in ref_ids]
        except ValueError:
            ref_int = []
        if ref_int and ref_int != sorted(ref_int):
            issues.append("脚注引用顺序与 id 升序不一致：%s" % ref_ids)
        ordered_defs = [i for i in def_ids if i in ref_ids]
        if ordered_defs != ref_ids:
            issues.append("脚注定义顺序与引用顺序不一致：def=%s ref=%s" % (def_ids, ref_ids))

    # 3) XML 仍可解析（tostring/fromstring 往返）
    for nm, root in (("document", document), ("footnotes", footnotes), ("styles", styles)):
        if root is None:
            continue
        try:
            etree.fromstring(etree.tostring(root))
        except etree.XMLSyntaxError as e:
            issues.append("%s.xml 解析失败：%s" % (nm, e))
    return issues


# --------------------------------------------------------------------------- #
# docx 包读写
# --------------------------------------------------------------------------- #
class Docx:
    def __init__(self, path):
        self.path = Path(path)
        self.members: dict[str, bytes] = {}
        self.order: list[str] = []
        with zipfile.ZipFile(self.path) as z:
            for info in z.infolist():
                self.order.append(info.filename)
                self.members[info.filename] = z.read(info.filename)
        self._trees: dict[str, object] = {}

    def tree(self, name):
        if name in self._trees:
            return self._trees[name]
        if name not in self.members:
            return None
        root = etree.fromstring(self.members[name])
        self._trees[name] = root
        return root

    def parsed(self, name):
        """已解析的树（未解析返回 None，不触发解析）——避免回写未改动文件。"""
        return self._trees.get(name)

    def text_part_names(self) -> list[str]:
        """All WordprocessingML parts in which reader-visible quote text may appear."""
        return [name for name in self.order if TEXT_PART_RE.match(name)]

    def save(self, out):
        for name, root in self._trees.items():
            self.members[name] = etree.tostring(
                root, xml_declaration=True, encoding="UTF-8", standalone=True
            )
        out = Path(out)
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for name in self.order:
                z.writestr(name, self.members[name])


# --------------------------------------------------------------------------- #
# 编排
# --------------------------------------------------------------------------- #
DEFAULT_SET = {"fonts", "quote_fonts", "footnotes", "indent", "wps"}
ALL_SET = DEFAULT_SET | {"smart_quotes", "headings", "citations", "tables", "grayscale"}


def normalize(
    docx: Docx,
    ops: set[str],
    heading_sizes=None,
    indent_missing=False,
    quote_locale_basis: str = "content",
) -> dict:
    document = docx.tree("word/document.xml")
    # 按需解析：styles/footnotes 只在相关 op 时才碰，避免回写时扰动未改动文件（issue #11）。
    styles = docx.tree("word/styles.xml") if ops & {"fonts", "wps"} else None
    footnotes = docx.tree("word/footnotes.xml") if "footnotes" in ops else None
    report = {}

    if "wps" in ops:
        report["wps_styles"] = fix_wps_styles(styles)
    if "fonts" in ops:
        report["eastasia_fonts"] = ensure_eastasia_fonts(document, styles)
    text_parts = docx.text_part_names() if ops & {"quote_fonts", "smart_quotes"} else []
    if "smart_quotes" in ops:
        report["smart_quotes"] = sum(smart_quotes(docx.tree(name)) for name in text_parts)
    if "quote_fonts" in ops:
        totals = {
            "quotes_routed": 0,
            "apostrophes_routed": 0,
            "runs_split": 0,
            "ambiguous_skipped": 0,
            "unsafe_runs_skipped": 0,
        }
        for name in text_parts:
            part_report = normalize_quote_fonts(docx.tree(name), locale_basis=quote_locale_basis)
            for key, value in part_report.items():
                totals[key] += value
        report["quote_fonts"] = totals
    if "headings" in ops:
        report["headings"] = dedup_heading_numbering(document, heading_sizes)
    if "citations" in ops:
        report["citations_merged"] = merge_citations(document)
        report["citations_superscript"] = superscript_citations(document)
    if "footnotes" in ops:
        report["footnotes_renumbered"] = reorder_footnotes(document, footnotes)
    if "tables" in ops:
        report["three_line_tables"] = make_three_line_tables(document)
    if "grayscale" in ops:
        report["grayscale_images"] = grayscale_images(document)
        report["drawing_line_fix"] = fix_drawing_line_spacing(document)
    if "indent" in ops:
        report["firstline_chars"] = firstline_chars(document, add_missing=indent_missing)

    # 总是兜底重排，保证 schema 顺序不变量
    reorder_all(document)
    for name in text_parts:
        root = docx.parsed(name)
        if root is not document:
            reorder_all(root)
    return report


def normalize_docx_quote_fonts(
    path: Path,
    *,
    locale_basis: str = "content",
) -> dict[str, int]:
    """Normalize generated DOCX quote runs in place, without touching character content."""
    package = Docx(path)
    report = normalize(package, {"quote_fonts"}, quote_locale_basis=locale_basis)["quote_fonts"]
    changed = report["quotes_routed"] + report["apostrophes_routed"] + report["runs_split"]
    if not changed:
        return report
    handle, raw_temp = tempfile.mkstemp(prefix=f".{path.stem}.quotes-", suffix=".docx", dir=str(path.parent))
    os.close(handle)
    temp_path = Path(raw_temp)
    try:
        package.save(temp_path)
        with zipfile.ZipFile(temp_path) as archive:
            etree.fromstring(archive.read("word/document.xml"))
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()
    return report


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def parse_args(argv):
    ap = argparse.ArgumentParser(description="中文投稿稿 docx OOXML 规范化")
    ap.add_argument("input", nargs="?", help="输入 .docx")
    ap.add_argument("output", nargs="?", help="输出 .docx（省略则在输入旁加 .fixed）")
    ap.add_argument("--all", action="store_true", help="启用全部修复（含破坏性项）")
    for op in ("fonts", "quote_fonts", "smart_quotes", "headings", "citations",
               "footnotes", "tables", "grayscale", "indent", "wps"):
        ap.add_argument("--" + op.replace("_", "-"), dest=op, action="store_true")
    ap.add_argument(
        "--quotes",
        action="store_true",
        help="兼容别名：同时启用 --quote-fonts 与 --smart-quotes（已弃用）",
    )
    ap.add_argument(
        "--quote-locale-basis",
        choices=("content", "host"),
        default="content",
        help="自动判定引号语言时按被引内容（默认）或宿主段落",
    )
    ap.add_argument("--indent-missing", action="store_true",
                    help="给无缩进正文段补 2 字首行缩进")
    ap.add_argument("--heading-sizes", default="",
                    help='按级设字号 half-point，如 "1=32,2=28,3=24"')
    ap.add_argument("--check", action="store_true", help="只校验不变量，不写文件")
    ap.add_argument("--sanitize", metavar="NAME", help="只输出合法化后的文件名")
    return ap.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])

    if args.sanitize is not None:
        print(sanitize_filename(args.sanitize))
        return 0

    if not args.input:
        print("错误：缺少输入 .docx", file=sys.stderr)
        return 2

    docx = Docx(args.input)

    if args.check:
        issues = validate(
            docx.tree("word/document.xml"),
            docx.tree("word/footnotes.xml"),
            docx.tree("word/styles.xml"),
        )
        if issues:
            print("不变量校验：发现 %d 处问题" % len(issues))
            for s in issues:
                print("  - " + s)
            return 1
        print("不变量校验：通过 ✓")
        return 0

    explicit = {op for op in ALL_SET if getattr(args, op, False)}
    if args.quotes:
        print("警告：--quotes 已弃用；请分别使用 --quote-fonts 和 --smart-quotes", file=sys.stderr)
        explicit.update({"quote_fonts", "smart_quotes"})
    if args.all:
        ops = set(ALL_SET)
    elif explicit:
        ops = explicit
    else:
        ops = set(DEFAULT_SET)

    heading_sizes = {}
    if args.heading_sizes:
        for pair in args.heading_sizes.split(","):
            k, _, v = pair.partition("=")
            if k.strip().isdigit() and v.strip().isdigit():
                heading_sizes[int(k)] = int(v)

    report = normalize(
        docx,
        ops,
        heading_sizes or None,
        args.indent_missing,
        args.quote_locale_basis,
    )

    # 输出路径 + 文件名合法化
    if args.output:
        out = Path(args.output)
    else:
        out = docx.path.with_name(docx.path.stem + ".fixed.docx")
    out = out.with_name(sanitize_filename(out.name))

    # 写前最后一道不变量校验（只看已解析的树，不额外触碰未改动文件）
    issues = validate(
        docx.tree("word/document.xml"),
        docx.parsed("word/footnotes.xml"),
        docx.parsed("word/styles.xml"),
    )
    docx.save(out)

    print("应用：" + ", ".join("%s=%s" % (k, v) for k, v in report.items()))
    print("输出：%s" % out)
    if issues:
        print("⚠ 校验发现 %d 处问题：" % len(issues))
        for s in issues:
            print("  - " + s)
        return 1
    print("不变量校验：通过 ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
